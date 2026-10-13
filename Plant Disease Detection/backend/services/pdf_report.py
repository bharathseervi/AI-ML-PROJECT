"""One-plant PDF report in English, Kannada or Hindi (ReportLab).

build_report(result, photo_bytes, lang) -> PDF bytes.
`result` is the JSON the /api/predict endpoint returned (label, confidence, rejected, top3, severity,
heatmap_png_b64, quality, ...). Kannada/Hindi text is drawn with HarfBuzz shaping, see typeset.py.
"""
import base64
import io
from datetime import datetime

from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from backend import disease_info as di
from backend.services import typeset

PAGE_W, PAGE_H = 595.27, 841.89  # A4 in points
MARGIN = 42
CONTENT_W = PAGE_W - 2 * MARGIN
BOTTOM = 58

INK = (0.13, 0.13, 0.13)
MUTED = (0.40, 0.40, 0.40)
GREEN = (0.10, 0.42, 0.22)
AMBER = (0.70, 0.40, 0.00)
RED = (0.70, 0.12, 0.12)
BAND = (0.10, 0.42, 0.22)
NOTE_BG = (0.96, 0.96, 0.92)

S = {
    "en": {
        "title": "Rice Leaf Disease Report", "date": "Date", "photo": "Your photo", "heatmap": "Where the model looked",
        "heatmap_note": "Red and yellow areas show where the model saw the strongest signs of the disease.",
        "diagnosis": "Diagnosis", "confidence": "Confidence", "top3": "Top 3 possibilities",
        "severity": "Severity", "sev_of_leaf": "of the visible leaf area looks affected",
        "sev_experimental": "Experimental, colour-based estimate. In our tests it did not reliably separate healthy from diseased leaves, and values under about 10% may be noise. Judge the whole field, not one leaf.",
        "sev_no_leaf": "Not enough green leaf was found in the photo to estimate severity.",
        "sev_healthy": "Severity is not calculated for a healthy leaf.",
        "sev_Mild": "Mild", "sev_Moderate": "Moderate", "sev_Severe": "Severe",
        "quality": "Photo quality warnings",
        "q_blurry": "The photo looks blurry. Hold the phone steady, tap the leaf to focus, and retake it.",
        "q_too_dark": "The photo is too dark. Move to natural daylight and retake it.",
        "q_overexposed": "The photo is overexposed (too bright or glare). Avoid direct sun and flash, then retake it.",
        "unable_title": "Unable to diagnose reliably",
        "unable_text": "The model was not confident enough to name a disease from this photo. Please retake the photo using the tips below. This report does not contain treatment advice because there is no reliable diagnosis.",
        "r_low_confidence": "The model was not confident enough.", "r_high_entropy": "The model could not settle on one clear answer.",
        "closest": "Closest possibilities (NOT reliable)",
        "tips_title": "Photo tips",
        "tips": ["Photograph one leaf at a time.", "Take a close-up so the spots fill most of the frame.", "Use a plain background, such as your hand or a sheet of paper.", "Use natural daylight. Avoid flash, deep shadow and glare."],
        "description": "About this disease", "symptoms": "Symptoms", "causes": "Causes and favouring conditions",
        "actions": "What to do now (for this severity)", "management": "Management",
        "cultural": "Cultural practices", "organic": "Organic and biological", "chemical": "Chemical",
        "prevention": "Prevention", "growth": "Growth recommendations",
        "nutrient": "Nutrient management", "water": "Water management", "spacing": "Spacing", "monitoring": "Monitoring",
        "sources": "Sources", "sources_note": "The advice was written from these pages. It has not been reviewed by an agronomist.",
        "disclaimer_title": "Important",
        "translation_note": "", "footer": "Decision-support tool only. Confirm with your local agriculture officer or KVK.", "page": "Page",
    },
    "kn": {
        "title": "ಭತ್ತದ ಎಲೆ ರೋಗ ವರದಿ", "date": "ದಿನಾಂಕ", "photo": "ನಿಮ್ಮ ಫೋಟೋ", "heatmap": "ಮಾದರಿ ಎಲ್ಲಿ ನೋಡಿತು",
        "heatmap_note": "ಕೆಂಪು ಮತ್ತು ಹಳದಿ ಪ್ರದೇಶಗಳು ಮಾದರಿಯು ರೋಗದ ಅತಿ ಬಲವಾದ ಲಕ್ಷಣಗಳನ್ನು ಕಂಡ ಸ್ಥಳಗಳನ್ನು ತೋರಿಸುತ್ತವೆ.",
        "diagnosis": "ರೋಗ ನಿರ್ಣಯ", "confidence": "ವಿಶ್ವಾಸ", "top3": "ಮೊದಲ 3 ಸಾಧ್ಯತೆಗಳು",
        "severity": "ತೀವ್ರತೆ", "sev_of_leaf": "ಕಾಣುವ ಎಲೆಯ ಭಾಗ ಬಾಧಿತವಾಗಿ ಕಾಣುತ್ತದೆ",
        "sev_experimental": "ಪ್ರಾಯೋಗಿಕ, ಬಣ್ಣದ ಆಧಾರದ ಅಂದಾಜು. ನಮ್ಮ ಪರೀಕ್ಷೆಗಳಲ್ಲಿ ಇದು ಆರೋಗ್ಯವಂತ ಮತ್ತು ರೋಗಪೀಡಿತ ಎಲೆಗಳನ್ನು ವಿಶ್ವಾಸಾರ್ಹವಾಗಿ ಬೇರ್ಪಡಿಸಲಿಲ್ಲ, ಮತ್ತು ಸುಮಾರು 10% ಕ್ಕಿಂತ ಕಡಿಮೆ ಮೌಲ್ಯಗಳು ಶಬ್ದವಾಗಿರಬಹುದು. ಒಂದು ಎಲೆಯನ್ನಲ್ಲ, ಇಡೀ ಹೊಲವನ್ನು ಗಮನಿಸಿ ನಿರ್ಣಯಿಸಿ.",
        "sev_no_leaf": "ತೀವ್ರತೆಯನ್ನು ಅಂದಾಜಿಸಲು ಫೋಟೋದಲ್ಲಿ ಸಾಕಷ್ಟು ಹಸಿರು ಎಲೆ ಕಂಡುಬರಲಿಲ್ಲ.",
        "sev_healthy": "ಆರೋಗ್ಯವಂತ ಎಲೆಗೆ ತೀವ್ರತೆಯನ್ನು ಲೆಕ್ಕ ಹಾಕುವುದಿಲ್ಲ.",
        "sev_Mild": "ಸೌಮ್ಯ", "sev_Moderate": "ಮಧ್ಯಮ", "sev_Severe": "ತೀವ್ರ",
        "quality": "ಫೋಟೋ ಗುಣಮಟ್ಟದ ಎಚ್ಚರಿಕೆಗಳು",
        "q_blurry": "ಫೋಟೋ ಮಂಜಾಗಿದೆ. ಫೋನ್ ಸ್ಥಿರವಾಗಿ ಹಿಡಿದು, ಎಲೆಯ ಮೇಲೆ ಟ್ಯಾಪ್ ಮಾಡಿ ಫೋಕಸ್ ಮಾಡಿ, ಮತ್ತೆ ತೆಗೆಯಿರಿ.",
        "q_too_dark": "ಫೋಟೋ ತುಂಬಾ ಕತ್ತಲೆಯಾಗಿದೆ. ನೈಸರ್ಗಿಕ ಹಗಲು ಬೆಳಕಿಗೆ ಹೋಗಿ ಮತ್ತೆ ತೆಗೆಯಿರಿ.",
        "q_overexposed": "ಫೋಟೋದಲ್ಲಿ ಬೆಳಕು ಹೆಚ್ಚಾಗಿದೆ (ಅತಿ ಪ್ರಕಾಶ ಅಥವಾ ಪ್ರತಿಫಲನ). ನೇರ ಸೂರ್ಯನ ಬೆಳಕು ಮತ್ತು ಫ್ಲ್ಯಾಶ್ ತಪ್ಪಿಸಿ, ಮತ್ತೆ ತೆಗೆಯಿರಿ.",
        "unable_title": "ವಿಶ್ವಾಸಾರ್ಹವಾಗಿ ಪತ್ತೆ ಮಾಡಲಾಗಲಿಲ್ಲ",
        "unable_text": "ಈ ಫೋಟೋದಿಂದ ರೋಗದ ಹೆಸರು ಹೇಳಲು ಮಾದರಿಗೆ ಸಾಕಷ್ಟು ವಿಶ್ವಾಸ ಇರಲಿಲ್ಲ. ಕೆಳಗಿನ ಸಲಹೆಗಳನ್ನು ಬಳಸಿ ಫೋಟೋವನ್ನು ಮತ್ತೆ ತೆಗೆಯಿರಿ. ವಿಶ್ವಾಸಾರ್ಹ ರೋಗ ನಿರ್ಣಯ ಇಲ್ಲದ ಕಾರಣ ಈ ವರದಿಯಲ್ಲಿ ಚಿಕಿತ್ಸೆಯ ಸಲಹೆ ಇಲ್ಲ.",
        "r_low_confidence": "ಮಾದರಿಗೆ ಸಾಕಷ್ಟು ವಿಶ್ವಾಸ ಇರಲಿಲ್ಲ.", "r_high_entropy": "ಮಾದರಿಗೆ ಒಂದು ಸ್ಪಷ್ಟ ಉತ್ತರ ಆರಿಸಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ.",
        "closest": "ಹತ್ತಿರದ ಸಾಧ್ಯತೆಗಳು (ವಿಶ್ವಾಸಾರ್ಹವಲ್ಲ)",
        "tips_title": "ಫೋಟೋ ಸಲಹೆಗಳು",
        "tips": ["ಒಂದು ಸಮಯದಲ್ಲಿ ಒಂದೇ ಎಲೆಯ ಫೋಟೋ ತೆಗೆಯಿರಿ.", "ಚುಕ್ಕೆಗಳು ಚೌಕಟ್ಟಿನ ಹೆಚ್ಚಿನ ಭಾಗ ತುಂಬುವಂತೆ ಹತ್ತಿರದಿಂದ ತೆಗೆಯಿರಿ.", "ನಿಮ್ಮ ಕೈ ಅಥವಾ ಕಾಗದದಂತಹ ಸರಳ ಹಿನ್ನೆಲೆ ಬಳಸಿ.", "ನೈಸರ್ಗಿಕ ಹಗಲು ಬೆಳಕನ್ನು ಬಳಸಿ. ಫ್ಲ್ಯಾಶ್, ಗಾಢ ನೆರಳು ಮತ್ತು ಪ್ರತಿಫಲನ ತಪ್ಪಿಸಿ."],
        "description": "ಈ ರೋಗದ ಬಗ್ಗೆ", "symptoms": "ಲಕ್ಷಣಗಳು", "causes": "ಕಾರಣಗಳು ಮತ್ತು ಅನುಕೂಲಕರ ಪರಿಸ್ಥಿತಿಗಳು",
        "actions": "ಈಗ ಏನು ಮಾಡಬೇಕು (ಈ ತೀವ್ರತೆಗೆ)", "management": "ನಿರ್ವಹಣೆ",
        "cultural": "ಬೇಸಾಯ ಕ್ರಮಗಳು", "organic": "ಸಾವಯವ ಮತ್ತು ಜೈವಿಕ", "chemical": "ರಾಸಾಯನಿಕ",
        "prevention": "ತಡೆಗಟ್ಟುವಿಕೆ", "growth": "ಬೆಳವಣಿಗೆ ಶಿಫಾರಸುಗಳು",
        "nutrient": "ಪೋಷಕಾಂಶ ನಿರ್ವಹಣೆ", "water": "ನೀರಿನ ನಿರ್ವಹಣೆ", "spacing": "ಅಂತರ", "monitoring": "ಮೇಲ್ವಿಚಾರಣೆ",
        "sources": "ಮೂಲಗಳು", "sources_note": "ಸಲಹೆಯನ್ನು ಈ ಪುಟಗಳಿಂದ ಬರೆಯಲಾಗಿದೆ. ಇದನ್ನು ಕೃಷಿ ವಿಜ್ಞಾನಿಯೊಬ್ಬರು ಪರಿಶೀಲಿಸಿಲ್ಲ.",
        "disclaimer_title": "ಮುಖ್ಯ",
        "translation_note": "ಈ ಅನುವಾದವನ್ನು AI ಮಾದರಿ ಬರೆದಿದೆ ಮತ್ತು ಸ್ಥಳೀಯ ಭಾಷಿಕರು ಇನ್ನೂ ಪರಿಶೀಲಿಸಿಲ್ಲ.",
        "footer": "ಇದು ನಿರ್ಧಾರ ಬೆಂಬಲ ಸಾಧನ ಮಾತ್ರ. ನಿಮ್ಮ ಸ್ಥಳೀಯ ಕೃಷಿ ಅಧಿಕಾರಿ ಅಥವಾ ಕೆವಿಕೆಯೊಂದಿಗೆ ಖಚಿತಪಡಿಸಿ.", "page": "ಪುಟ",
    },
    "hi": {
        "title": "धान पत्ती रोग रिपोर्ट", "date": "तारीख", "photo": "आपकी फोटो", "heatmap": "मॉडल ने कहाँ देखा",
        "heatmap_note": "लाल और पीले हिस्से दिखाते हैं कि मॉडल को रोग के सबसे मज़बूत संकेत कहाँ दिखे।",
        "diagnosis": "निदान", "confidence": "विश्वास", "top3": "शीर्ष 3 संभावनाएँ",
        "severity": "गंभीरता", "sev_of_leaf": "दिखाई देने वाली पत्ती का हिस्सा प्रभावित दिखता है",
        "sev_experimental": "प्रायोगिक, रंग पर आधारित अनुमान। हमारे परीक्षणों में यह स्वस्थ और रोगग्रस्त पत्तियों को भरोसेमंद ढंग से अलग नहीं कर सका, और लगभग 10% से कम मान शोर हो सकते हैं। एक पत्ती नहीं, पूरे खेत को देखकर निर्णय लें।",
        "sev_no_leaf": "गंभीरता का अनुमान लगाने के लिए फोटो में पर्याप्त हरी पत्ती नहीं मिली।",
        "sev_healthy": "स्वस्थ पत्ती के लिए गंभीरता की गणना नहीं की जाती।",
        "sev_Mild": "हल्की", "sev_Moderate": "मध्यम", "sev_Severe": "गंभीर",
        "quality": "फोटो की गुणवत्ता की चेतावनियाँ",
        "q_blurry": "फोटो धुंधली है। फोन को स्थिर रखें, पत्ती पर टैप करके फोकस करें और दोबारा फोटो लें।",
        "q_too_dark": "फोटो बहुत अंधेरी है। प्राकृतिक दिन की रोशनी में जाकर दोबारा फोटो लें।",
        "q_overexposed": "फोटो में रोशनी बहुत अधिक है (तेज़ चमक या ग्लेयर)। सीधी धूप और फ्लैश से बचें और दोबारा फोटो लें।",
        "unable_title": "भरोसेमंद पहचान नहीं हो सकी",
        "unable_text": "इस फोटो से रोग का नाम बताने के लिए मॉडल को पर्याप्त भरोसा नहीं था। कृपया नीचे दिए सुझावों के अनुसार फोटो दोबारा लें। भरोसेमंद निदान न होने के कारण इस रिपोर्ट में उपचार की सलाह नहीं है।",
        "r_low_confidence": "मॉडल को पर्याप्त भरोसा नहीं था।", "r_high_entropy": "मॉडल एक स्पष्ट उत्तर नहीं चुन सका।",
        "closest": "निकटतम संभावनाएँ (भरोसेमंद नहीं)",
        "tips_title": "फोटो के सुझाव",
        "tips": ["एक बार में केवल एक पत्ती की फोटो लें।", "पास से फोटो लें ताकि धब्बे फ्रेम का अधिकांश भाग भर दें।", "सादी पृष्ठभूमि रखें, जैसे आपका हाथ या सफेद कागज।", "प्राकृतिक दिन की रोशनी में फोटो लें। फ्लैश, गहरी छाया और चमक से बचें।"],
        "description": "इस रोग के बारे में", "symptoms": "लक्षण", "causes": "कारण और अनुकूल परिस्थितियाँ",
        "actions": "अभी क्या करें (इस गंभीरता के लिए)", "management": "प्रबंधन",
        "cultural": "कृषि पद्धतियाँ", "organic": "जैविक और जैव-नियंत्रण", "chemical": "रासायनिक",
        "prevention": "रोकथाम", "growth": "वृद्धि संबंधी सुझाव",
        "nutrient": "पोषक तत्व प्रबंधन", "water": "जल प्रबंधन", "spacing": "दूरी", "monitoring": "निगरानी",
        "sources": "स्रोत", "sources_note": "सलाह इन पृष्ठों से लिखी गई है। इसकी समीक्षा किसी कृषि वैज्ञानिक ने नहीं की है।",
        "disclaimer_title": "महत्वपूर्ण",
        "translation_note": "यह अनुवाद एक AI मॉडल ने लिखा है और किसी मूल भाषी ने इसकी समीक्षा अभी नहीं की है।",
        "footer": "यह केवल निर्णय में सहायता करने वाला उपकरण है। अपने स्थानीय कृषि अधिकारी या केवीके से पुष्टि करें।", "page": "पृष्ठ",
    },
}


class _Doc:
    """Tiny top-down flow layout on a ReportLab canvas."""

    def __init__(self, lang: str, title: str, when: str):
        self.lang, self.str = lang, S[lang]
        self.ts = typeset.typesetter_for(lang)
        self.buf = io.BytesIO()
        self.c = canvas.Canvas(self.buf, pagesize=(PAGE_W, PAGE_H), pageCompression=1)
        self.c.setTitle(title)
        self.c.setAuthor("Rice Leaf Disease Detection")
        self.page = 0
        self.title, self.when = title, when
        self._new_page(first=True)

    # ---- pages -------------------------------------------------------------------------
    def _new_page(self, first=False):
        if not first:
            self._footer()
            self.c.showPage()
        self.page += 1
        self.y = PAGE_H - MARGIN
        if first:  # header band on page 1 only
            self.c.setFillColorRGB(*BAND)
            self.c.rect(0, PAGE_H - 70, PAGE_W, 70, stroke=0, fill=1)
            self.ts.draw(self.c, MARGIN, PAGE_H - 36, self.title, 20, (1, 1, 1), True)
            self.ts.draw(self.c, MARGIN, PAGE_H - 56, f"{self.str['date']}: {self.when}", 10, (1, 1, 1))
            self.y = PAGE_H - 70 - 22

    def _footer(self):
        self.c.setStrokeColorRGB(0.8, 0.8, 0.8)
        self.c.setLineWidth(0.5)
        self.c.line(MARGIN, 44, PAGE_W - MARGIN, 44)
        for i, ln in enumerate(typeset.wrap(self.ts, self.str["footer"], 8, CONTENT_W - 60)):
            self.ts.draw(self.c, MARGIN, 32 - i * 10, ln, 8, MUTED)
        label = f"{self.str['page']} {self.page}"
        self.ts.draw(self.c, PAGE_W - MARGIN - self.ts.width(label, 8), 32, label, 8, MUTED)

    def ensure(self, h: float):
        if self.y - h < BOTTOM:
            self._new_page()

    def gap(self, h=6):
        self.y -= h

    # ---- text --------------------------------------------------------------------------
    def para(self, text, size=10, color=INK, bold=False, indent=0, leading=1.45, x_extra=0):
        width = CONTENT_W - indent - x_extra
        for ln in typeset.wrap(self.ts, text, size, width, bold):
            self.ensure(size * leading)
            self.y -= size * leading
            self.ts.draw(self.c, MARGIN + indent + x_extra, self.y, ln, size, color, bold)

    def heading(self, text):
        self.ensure(62)  # keep the heading together with the first lines under it
        self.gap(10)
        self.y -= 14
        self.ts.draw(self.c, MARGIN, self.y, text, 13, GREEN, True)
        self.y -= 4
        self.c.setStrokeColorRGB(*GREEN)
        self.c.setLineWidth(0.8)
        self.c.line(MARGIN, self.y, PAGE_W - MARGIN, self.y)
        self.gap(3)

    def subheading(self, text):
        self.ensure(26)
        self.gap(4)
        self.para(text, 10.5, INK, True)

    def bullets(self, items, size=10, color=INK):
        for it in items:
            lines = typeset.wrap(self.ts, it, size, CONTENT_W - 14)
            self.ensure(size * 1.45 * min(len(lines), 2))
            for i, ln in enumerate(lines):
                self.ensure(size * 1.45)
                self.y -= size * 1.45
                if i == 0:
                    self.ts.draw(self.c, MARGIN + 3, self.y, "•", size, GREEN)
                self.ts.draw(self.c, MARGIN + 14, self.y, ln, size, color)
            self.gap(1.5)

    def note_box(self, title, text, color=AMBER):
        size = 9.5
        lines = typeset.wrap(self.ts, text, size, CONTENT_W - 20)
        h = len(lines) * size * 1.45 + (22 if title else 12)
        self.ensure(h + 8)
        self.gap(6)
        top = self.y
        self.c.setFillColorRGB(*NOTE_BG)
        self.c.setStrokeColorRGB(*color)
        self.c.setLineWidth(1)
        self.c.roundRect(MARGIN, top - h, CONTENT_W, h, 4, stroke=1, fill=1)
        yy = top - 8
        if title:
            yy -= 10
            self.ts.draw(self.c, MARGIN + 10, yy, title, 10, color, True)
            yy -= 3
        for ln in lines:
            yy -= size * 1.45
            self.ts.draw(self.c, MARGIN + 10, yy, ln, size, INK)
        self.y = top - h - 4

    # ---- images ------------------------------------------------------------------------
    def image_pair(self, left, right):
        """left/right: (PIL image or None, caption). Draws up to two images side by side."""
        col_w, max_h = (CONTENT_W - 14) / 2, 215
        items = [it for it in (left, right) if it and it[0] is not None]
        if not items:
            return
        drawn = []
        for img, cap in items:
            iw, ih = img.size
            s = min(col_w / iw, max_h / ih)
            drawn.append((img, cap, iw * s, ih * s))
        block_h = max(d[3] for d in drawn) + 28
        self.ensure(block_h)
        top = self.y
        for i, (img, cap, w, h) in enumerate(drawn):
            x = MARGIN + i * (col_w + 14)
            buf = io.BytesIO()
            img.convert("RGB").save(buf, "JPEG", quality=85)
            buf.seek(0)
            self.c.drawImage(ImageReader(buf), x, top - h, w, h)
            self.c.setStrokeColorRGB(0.8, 0.8, 0.8)
            self.c.rect(x, top - h, w, h, stroke=1, fill=0)
            self.ts.draw(self.c, x, top - h - 12, cap, 9, MUTED)
        self.y = top - block_h

    def finish(self) -> bytes:
        self._footer()
        self.c.showPage()
        self.c.save()
        return self.buf.getvalue()


def _load_image(data: bytes, max_side=900):
    img = Image.open(io.BytesIO(data))
    img.load()
    img.thumbnail((max_side, max_side))
    return img


def _pct(x) -> str:
    return f"{float(x) * 100:.1f}%"


def build_report(result: dict, photo_bytes: bytes, lang: str = "en", now: datetime | None = None) -> bytes:
    lang = lang if lang in S else "en"
    st = S[lang]
    when = (now or datetime.now()).strftime("%d-%m-%Y %H:%M")
    names = di.names(lang)

    rejected = bool(result.get("rejected")) or not result.get("label")
    label = None if rejected else result["label"]
    sev = result.get("severity") or None
    level = sev.get("level") if sev and sev.get("leaf_found") else None
    info = di.get_info(label, lang, level) if label else None
    if label and info is None:
        raise ValueError(f"unknown label: {label!r}")

    doc = _Doc(lang, st["title"], when)

    # ---- pictures ----
    photo = _load_image(photo_bytes) if photo_bytes else None
    heat = None
    if not rejected and result.get("heatmap_png_b64"):
        try:
            heat = _load_image(base64.b64decode(result["heatmap_png_b64"]))
        except Exception:  # a damaged heatmap must not stop the report
            heat = None
    doc.image_pair((photo, st["photo"]), (heat, st["heatmap"]) if heat else None)
    if heat:
        doc.para(st["heatmap_note"], 8.5, MUTED)

    # ---- quality warnings ----
    issues = (result.get("quality") or {}).get("issues", [])
    if issues:
        doc.heading(st["quality"])
        doc.bullets([st[f"q_{i}"] for i in issues if f"q_{i}" in st], 10, AMBER)

    top3 = result.get("top3") or []

    # ---- rejected: no diagnosis, no treatment advice ----
    if rejected:
        doc.heading(st["unable_title"])
        doc.para(st["unable_text"])
        for r in result.get("reject_reasons") or []:
            if f"r_{r}" in st:
                doc.para(st[f"r_{r}"], 10, MUTED)
        if top3:
            doc.subheading(st["closest"])
            doc.bullets([f"{names.get(t['label'], t['label'])}: {_pct(t['confidence'])}" for t in top3], 10, MUTED)
        doc.heading(st["tips_title"])
        doc.bullets(st["tips"])
        doc.heading(st["disclaimer_title"])
        doc.note_box("", di.DISCLAIMER[lang], RED)
        if st["translation_note"]:
            doc.para(st["translation_note"], 8.5, MUTED)
        return doc.finish()

    # ---- diagnosis ----
    doc.heading(st["diagnosis"])
    doc.gap(2)
    doc.para(info["name"], 17, INK, True, leading=1.3)
    doc.para(f"{st['confidence']}: {_pct(result.get('confidence', 0))}", 11, INK)
    if top3:
        doc.subheading(st["top3"])
        doc.bullets([f"{names.get(t['label'], t['label'])}: {_pct(t['confidence'])}" for t in top3])

    # ---- severity ----
    doc.heading(st["severity"])
    if label == "Healthy":
        doc.para(st["sev_healthy"])
    elif sev and sev.get("leaf_found"):
        doc.para(f"{st['sev_' + level]}: {float(sev['percent']):.1f}% {st['sev_of_leaf']}", 11, INK, True)
        doc.note_box("", st["sev_experimental"], AMBER)
    else:
        doc.para(st["sev_no_leaf"])
    if info["severity_advice"]:
        doc.subheading(st["actions"])
        doc.bullets(info["severity_advice"])

    # ---- knowledge base ----
    doc.heading(st["description"])
    doc.para(info["description"])
    for key, title in (("symptoms", "symptoms"), ("causes", "causes")):
        if info[key]:
            doc.heading(st[title])
            doc.bullets(info[key])

    mg = info["management"]
    if any(mg.values()):
        doc.heading(st["management"])
        for key in ("cultural", "organic", "chemical"):
            if mg[key]:
                doc.subheading(st[key])
                doc.bullets(mg[key])

    if info["prevention"]:
        doc.heading(st["prevention"])
        doc.bullets(info["prevention"])

    doc.heading(st["growth"])
    for key in ("nutrient", "water", "spacing", "monitoring"):
        if info["growth"][key]:
            doc.subheading(st[key])
            doc.bullets(info["growth"][key])

    # ---- sources and disclaimer ----
    doc.heading(st["sources"])
    doc.para(st["sources_note"], 9, MUTED)
    for s in info["sources"]:
        doc.para(f"{s['org']}: {s['title']}", 8.5, INK, indent=8)
        doc.para(s["url"], 7.5, MUTED, indent=8, leading=1.3)
    doc.heading(st["disclaimer_title"])
    doc.note_box("", info["disclaimer"], RED)
    if st["translation_note"]:
        doc.para(st["translation_note"], 8.5, MUTED)
    return doc.finish()
