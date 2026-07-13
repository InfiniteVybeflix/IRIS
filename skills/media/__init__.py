"""IRIS Media Skills — Music control, image editor/generation, audio transcription/editor, screenshot, screen control."""
from skills.media.music_control.skill import MusicControlSkill
from skills.media.image_editor.skill import ImageEditorSkill
from skills.media.image_generation.skill import ImageGenerationSkill
from skills.media.audio_transcription.skill import AudioTranscriptionSkill
from skills.media.audio_editor.skill import AudioEditorSkill
from skills.media.screenshot_analysis.skill import ScreenshotAnalysisSkill
from skills.media.screen_control.skill import ScreenControlSkill
__all__ = [MusicControlSkill, ImageEditorSkill, ImageGenerationSkill, AudioTranscriptionSkill, AudioEditorSkill, ScreenshotAnalysisSkill, ScreenControlSkill]
