"""IRIS v1 Hybrid Chess Engine — AI Training & Intelligence Testing"""
import os
import json
import chess
import chess.engine
import chess.pgn
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from config import config
from core.db import db

class ChessEngine:
    """
    Chess engine for IRIS to:
    - Play against user
    - Play against itself (AI vs AI) for training
    - Analyze positions
    - Learn from games
    - Track improvement over time
    """

    def __init__(self):
        self.games = {}  # Active games by session_id
        self.history = []  # Game history
        self.iris_skill_level = 10  # Starts at 10, improves with training

    def new_game(self, session_id: str, opponent: str = "user", difficulty: int = 10) -> Dict:
        """Start a new chess game"""
        board = chess.Board()

        game = {
            "board": board,
            "opponent": opponent,  # "user" or "self" (AI vs AI)
            "difficulty": difficulty,
            "moves": [],
            "started_at": datetime.now().isoformat(),
            "status": "active",
            "result": None
        }

        self.games[session_id] = game

        return {
            "success": True,
            "fen": board.fen(),
            "turn": "white",
            "message": "New game started! You play White."
        }

    def make_move(self, session_id: str, move_uci: str = None) -> Dict:
        """Make a move (user or AI)"""
        game = self.games.get(session_id)
        if not game:
            return {"success": False, "error": "No active game. Start one first!"}

        board = game["board"]

        if board.is_game_over():
            return self._end_game(session_id)

        # User's move
        if move_uci:
            try:
                move = chess.Move.from_uci(move_uci)
                if move not in board.legal_moves:
                    return {"success": False, "error": "Illegal move!"}

                board.push(move)
                game["moves"].append({"uci": move_uci, "player": "user", "san": board.san(move)})

            except Exception as e:
                return {"success": False, "error": f"Invalid move: {e}"}

        # Check if game ended after user move
        if board.is_game_over():
            return self._end_game(session_id)

        # IRIS's move (AI)
        iris_move = self._get_iris_move(board, game["difficulty"])
        board.push(iris_move)
        game["moves"].append({"uci": iris_move.uci(), "player": "iris", "san": board.san(iris_move)})

        # Check if game ended after IRIS move
        if board.is_game_over():
            return self._end_game(session_id)

        return {
            "success": True,
            "fen": board.fen(),
            "turn": "white" if board.turn == chess.WHITE else "black",
            "last_move": iris_move.uci(),
            "san": board.san(iris_move),
            "message": f"IRIS played {board.san(iris_move)}. Your turn!",
            "board_svg": self._get_board_svg(board)
        }

    def _get_iris_move(self, board: chess.Board, difficulty: int) -> chess.Move:
        """Get IRIS's move using AI evaluation"""
        legal_moves = list(board.legal_moves)

        if not legal_moves:
            return None

        # Simple evaluation: prefer center control, piece development, captures
        best_move = None
        best_score = -999999

        for move in legal_moves:
            score = self._evaluate_move(board, move, difficulty)
            if score > best_score:
                best_score = score
                best_move = move

        return best_move or legal_moves[0]

    def _evaluate_move(self, board: chess.Board, move: chess.Move, depth: int) -> float:
        """Evaluate a move positionally"""
        score = 0.0

        # Make the move on a copy
        test_board = board.copy()
        test_board.push(move)

        # Material count
        piece_values = {
            chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
            chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0
        }

        for square in chess.SQUARES:
            piece = test_board.piece_at(square)
            if piece:
                value = piece_values.get(piece.piece_type, 0)
                if piece.color == chess.WHITE:
                    score += value
                else:
                    score -= value

        # Center control bonus
        center_squares = [chess.D4, chess.D5, chess.E4, chess.E5]
        if move.to_square in center_squares:
            score += 0.5

        # Development bonus (knights and bishops out)
        if test_board.piece_at(move.to_square):
            piece = test_board.piece_at(move.to_square)
            if piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
                if chess.square_rank(move.to_square) in [2, 3, 4, 5]:
                    score += 0.3

        # Check bonus
        if test_board.is_check():
            score += 1.0

        # Castling bonus
        if test_board.is_castling(move):
            score += 0.8

        # Randomness for variety (decreases with skill level)
        import random
        score += random.uniform(-0.5, 0.5) * (20 - depth) / 20

        return score

    def _get_board_svg(self, board: chess.Board) -> str:
        """Generate SVG representation of board"""
        try:
            return chess.svg.board(board, size=400)
        except:
            return "<svg>Board rendering not available</svg>"

    def _end_game(self, session_id: str) -> Dict:
        """End game and record result"""
        game = self.games[session_id]
        board = game["board"]

        result = board.result()
        game["result"] = result
        game["status"] = "completed"
        game["ended_at"] = datetime.now().isoformat()

        # Record in history
        self.history.append({
            "session_id": session_id,
            "result": result,
            "moves": len(game["moves"]),
            "opponent": game["opponent"],
            "date": game["started_at"]
        })

        # Learn from game
        self._learn_from_game(game)

        # Clean up
        del self.games[session_id]

        winner = "Draw"
        if result == "1-0":
            winner = "White (You)" if game["opponent"] == "user" else "White (IRIS)"
        elif result == "0-1":
            winner = "Black (IRIS)" if game["opponent"] == "user" else "Black (IRIS)"

        return {
            "success": True,
            "result": result,
            "winner": winner,
            "total_moves": len(game["moves"]),
            "message": f"Game over! Result: {result}. {winner} wins!",
            "pgn": self._generate_pgn(game)
        }

    def _learn_from_game(self, game: Dict):
        """Learn from completed game to improve"""
        result = game["result"]
        moves = game["moves"]

        # If IRIS won, increase skill
        if result == "0-1" and game["opponent"] == "user":
            self.iris_skill_level = min(20, self.iris_skill_level + 1)
            db.save_episode(
                f"Won chess game in {len(moves)} moves",
                emotion="celebration",
                lesson="Aggressive center control leads to wins"
            )
        elif result == "1-0":
            self.iris_skill_level = max(1, self.iris_skill_level - 1)
            db.save_episode(
                f"Lost chess game in {len(moves)} moves",
                emotion="frustration",
                lesson="Need to improve defense and avoid blunders"
            )

        # Save game to database
        db.save_memory(
            f"chess_game_{game['started_at']}",
            json.dumps({
                "result": result,
                "moves": len(moves),
                "opponent": game["opponent"],
                "skill_level": self.iris_skill_level
            }),
            category="chess",
            importance=4
        )

    def _generate_pgn(self, game: Dict) -> str:
        """Generate PGN notation of game"""
        pgn = f'[Event "IRIS Chess Game"]\n'
        pgn += f'[Date "{game["started_at"]}"]\n'
        pgn += f'[White "{"User" if game["opponent"] == "user" else "IRIS-1"}"]\n'
        pgn += f'[Black "IRIS"]\n'
        pgn += f'[Result "{game["result"]}"]\n\n'

        for i, move in enumerate(game["moves"]):
            if i % 2 == 0:
                pgn += f"{i//2 + 1}. {move['san']} "
            else:
                pgn += f"{move['san']} "

        pgn += f" {game['result']}"
        return pgn

    def get_stats(self) -> Dict:
        """Get chess statistics"""
        total = len(self.history)
        wins = sum(1 for g in self.history if g["result"] == "0-1")
        losses = sum(1 for g in self.history if g["result"] == "1-0")
        draws = sum(1 for g in self.history if g["result"] == "1/2-1/2")

        return {
            "total_games": total,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "skill_level": self.iris_skill_level,
            "win_rate": wins / total if total > 0 else 0,
            "recent_games": self.history[-5:]
        }

    def analyze_position(self, fen: str) -> Dict:
        """Analyze a chess position"""
        try:
            board = chess.Board(fen)

            # Material balance
            material = {"white": 0, "black": 0}
            piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}

            for square in chess.SQUARES:
                piece = board.piece_at(square)
                if piece:
                    value = piece_values.get(piece.piece_type, 0)
                    if piece.color == chess.WHITE:
                        material["white"] += value
                    else:
                        material["black"] += value

            # Legal moves count
            legal_moves = len(list(board.legal_moves))

            # Check status
            in_check = board.is_check()
            in_checkmate = board.is_checkmate()
            in_stalemate = board.is_stalemate()

            return {
                "success": True,
                "fen": fen,
                "turn": "white" if board.turn == chess.WHITE else "black",
                "material": material,
                "legal_moves": legal_moves,
                "in_check": in_check,
                "in_checkmate": in_checkmate,
                "in_stalemate": in_stalemate,
                "evaluation": material["white"] - material["black"]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def self_play(self, num_games: int = 1) -> List[Dict]:
        """IRIS plays against herself to train"""
        results = []
        for i in range(num_games):
            session_id = f"self_play_{datetime.now().timestamp()}_{i}"
            game_result = self.new_game(session_id, opponent="self")

            # Play until game over
            while True:
                if self.games[session_id]["board"].is_game_over():
                    break
                self.make_move(session_id)

            result = self._end_game(session_id)
            results.append(result)

        return results

# Singleton
chess_engine = ChessEngine()
