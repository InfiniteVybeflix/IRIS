"""IRIS Utilities Skills — Calculator, converters, weather, clock, translation, OCR, documents, files, QR."""
from skills.utilities.calculator.skill import CalculatorSkill
from skills.utilities.unit_converter.skill import UnitConverterSkill
from skills.utilities.currency_converter.skill import CurrencyConverterSkill
from skills.utilities.weather.skill import WeatherSkill
from skills.utilities.clock_worldtime.skill import ClockWorldtimeSkill
from skills.utilities.translation.skill import TranslationSkill
from skills.utilities.ocr.skill import OcrSkill
from skills.utilities.document_reader.skill import DocumentReaderSkill
from skills.utilities.file_manager.skill import FileManagerSkill
from skills.utilities.qr_scanner.skill import QrScannerSkill
__all__ = [CalculatorSkill, UnitConverterSkill, CurrencyConverterSkill, WeatherSkill, ClockWorldtimeSkill, TranslationSkill, OcrSkill, DocumentReaderSkill, FileManagerSkill, QrScannerSkill]
