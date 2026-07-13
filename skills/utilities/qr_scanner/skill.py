"""QR Scanner Skill — Generate and read QR codes and barcodes."""
import logging
from typing import Dict, Any
from skills import BaseSkill
logger = logging.getLogger(__name__)

class QrScannerSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="qr_scanner", category="utilities", capabilities=["qr_scanner"])

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "generate")
        if method == "generate": return self.generate(params)
        elif method == "read": return self.read(params)
        return {"error": f"Unknown method: {method}"}

    def generate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        data = params.get("data", "")
        if not data: return {"success": False, "error": "No data provided"}
        try:
            import qrcode
            import io
            import base64
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            b64 = base64.b64encode(buf.getvalue()).decode()
            return {"success": True, "data": data, "base64_png": b64}
        except ImportError:
            return {"success": False, "error": "qrcode and Pillow required. Install: pip install qrcode Pillow"}

    def read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        image_path = params.get("image_path", "")
        if not image_path: return {"success": False, "error": "No image path provided"}
        try:
            from pyzbar.pyzbar import decode
            from PIL import Image
            img = Image.open(image_path)
            results = decode(img)
            return {"success": True, "codes": [{"data": r.data.decode(), "type": r.type} for r in results], "count": len(results)}
        except ImportError:
            return {"success": False, "error": "pyzbar and Pillow required. Install: pip install pyzbar Pillow"}
