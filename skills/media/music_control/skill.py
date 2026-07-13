"""Music Control Skill — Control music playback, playlists."""
import logging
from typing import Dict, Any, List
from skills import BaseSkill
logger = logging.getLogger(__name__)

class MusicControlSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="music_control", category="media", capabilities=["music_control"])
        self._playlist: List[Dict[str, Any]] = []
        self._current_index = 0
        self._playing = False
        self._volume = 50

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "play")
        if method == "play": return self.play(params)
        elif method == "pause": return self.pause(params)
        elif method == "next": return self.next(params)
        elif method == "previous": return self.previous(params)
        elif method == "volume": return self.set_volume(params)
        elif method == "queue": return self.queue(params)
        elif method == "playlist": return self.get_playlist(params)
        return {"error": f"Unknown method: {method}"}

    def play(self, params: Dict[str, Any]) -> Dict[str, Any]:
        track = params.get("track", "")
        if track:
            self._playlist.insert(self._current_index, {"title": track, "artist": params.get("artist", ""), "duration": params.get("duration", 0)})
        self._playing = True
        current = self._playlist[self._current_index] if self._playlist else None
        return {"success": True, "playing": self._playing, "current_track": current}

    def pause(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self._playing = False
        return {"success": True, "playing": False}

    def next(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if self._current_index < len(self._playlist) - 1:
            self._current_index += 1
        return {"success": True, "current_track": self._playlist[self._current_index] if self._playlist else None}

    def previous(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if self._current_index > 0:
            self._current_index -= 1
        return {"success": True, "current_track": self._playlist[self._current_index] if self._playlist else None}

    def set_volume(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self._volume = max(0, min(100, params.get("level", 50)))
        return {"success": True, "volume": self._volume}

    def queue(self, params: Dict[str, Any]) -> Dict[str, Any]:
        track = {"title": params.get("title", ""), "artist": params.get("artist", ""), "duration": params.get("duration", 0)}
        self._playlist.append(track)
        return {"success": True, "queued": True, "position": len(self._playlist)}

    def get_playlist(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"success": True, "tracks": self._playlist, "current_index": self._current_index, "playing": self._playing}
