"""Knowledge base: disease information and growth recommendations in English, Kannada and Hindi.

READ THIS BEFORE USING THE CONTENT
* The agronomy was written from the sources listed in SOURCES (IRRI Rice Knowledge Bank, TNAU Agritech
  Portal). It was NOT reviewed by an agronomist. Have your guide or a KVK / agriculture officer check it.
* Kannada (kn) and Hindi (hi) are AI-written and NEED NATIVE-SPEAKER REVIEW (names of diseases included).
* No pesticide doses appear anywhere. Chemical names are only examples taken from the sources; products,
  doses and safety must follow the product label and local registration.
* Leaf Smut: no IRRI / TNAU page was found. Its content comes from US university extension sources
  (Texas A&M, University of Arkansas), which describe it as a minor late-season disease. Verify locally.
* Variety names and recommendations differ between regions and years; the text sends users to local offices.

Structure
    INFO[label][lang] -> {name, description, symptoms[], causes[], cultural[], organic[], chemical[],
                          prevention[], nutrient[], water[], spacing[], monitoring[]}
    COMMON[lang]      -> growth advice that applies to every diagnosis (nutrient, water, spacing, monitoring)
    SEVERITY[lang]    -> advice per severity level ("None", "Mild", "Moderate", "Severe")
    get_info(label, lang, severity) combines them into one dictionary for the API and the PDF.
"""

LANGS = ("en", "kn", "hi")
DEFAULT_LANG = "en"

SOURCES = {
    "irri_brown_spot": {"org": "IRRI Rice Knowledge Bank", "title": "Brown spot", "url": "http://www.knowledgebank.irri.org/training/fact-sheets/pest-management/diseases/item/brown-spot"},
    "irri_blast_leaf": {"org": "IRRI Rice Knowledge Bank", "title": "Blast (leaf and collar)", "url": "http://www.knowledgebank.irri.org/training/fact-sheets/pest-management/diseases/item/blast-leaf-collar"},
    "irri_blast_neck": {"org": "IRRI Rice Knowledge Bank", "title": "Blast (node and neck)", "url": "http://www.knowledgebank.irri.org/training/fact-sheets/pest-management/diseases/item/blast-node-neck"},
    "irri_tungro": {"org": "IRRI Rice Knowledge Bank", "title": "Tungro", "url": "http://www.knowledgebank.irri.org/training/fact-sheets/pest-management/diseases/item/tungro"},
    "irri_glh": {"org": "IRRI Rice Knowledge Bank", "title": "Green leafhopper", "url": "http://www.knowledgebank.irri.org/training/fact-sheets/pest-management/insects/item/green-leafhopper"},
    "irri_sheath_blight": {"org": "IRRI Rice Knowledge Bank", "title": "Sheath blight", "url": "http://www.knowledgebank.irri.org/training/fact-sheets/pest-management/diseases/item/sheath-blight"},
    "irri_n_excess": {"org": "IRRI Rice Knowledge Bank", "title": "Nitrogen (N) excess", "url": "http://www.knowledgebank.irri.org/training/fact-sheets/nutrient-management/deficiencies-and-toxicities-fact-sheet/item/nitrogen-excess"},
    "irri_awd": {"org": "IRRI Rice Knowledge Bank", "title": "Saving water with alternate wetting and drying (AWD)", "url": "http://www.knowledgebank.irri.org/training/fact-sheets/water-management/saving-water-alternate-wetting-drying-awd"},
    "tnau_blast": {"org": "TNAU Agritech Portal", "title": "Blast (Pyricularia oryzae)", "url": "http://www.agritech.tnau.ac.in/expert_system/paddy/cpdisblast.html"},
    "tnau_brown_spot": {"org": "TNAU Agritech Portal", "title": "Brown spot (Helminthosporium oryzae)", "url": "http://www.agritech.tnau.ac.in/expert_system/paddy/cpdisbrownspot.html"},
    "tnau_tungro": {"org": "TNAU Agritech Portal", "title": "Tungro", "url": "http://www.agritech.tnau.ac.in/expert_system/paddy/cpdistungro.html"},
    "tnau_sheath_blight": {"org": "TNAU Agritech Portal", "title": "Sheath blight (Rhizoctonia solani)", "url": "http://www.agritech.tnau.ac.in/expert_system/paddy/cpdissheathblight.html"},
    "tnau_diseases_pdf": {"org": "TNAU Agritech Portal", "title": "Management of diseases of important agricultural crops of Tamil Nadu", "url": "https://agritech.tnau.ac.in/pdf/8.pdf"},
    "tamu_rice": {"org": "Texas A&M Plant Disease Handbook", "title": "Rice (leaf smut)", "url": "https://plantdiseasehandbook.tamu.edu/food-crops/cereal-crops/rice/"},
    "uaex_rice": {"org": "University of Arkansas Extension", "title": "Rice disease management", "url": "https://www.uaex.uada.edu/farm-ranch/pest-management/plant-disease/rice.aspx"},
}

# Which sources each diagnosis' content came from (the general growth advice also uses irri_n_excess, irri_awd).
SOURCE_IDS = {
    "Blast": ["irri_blast_leaf", "irri_blast_neck", "tnau_blast", "tnau_diseases_pdf"],
    "Brown Spot": ["irri_brown_spot", "tnau_brown_spot", "tnau_diseases_pdf"],
    "Tungro": ["irri_tungro", "irri_glh", "tnau_tungro"],
    "Sheath Blight": ["irri_sheath_blight", "tnau_sheath_blight", "tnau_diseases_pdf"],
    "Leaf Smut": ["tamu_rice", "uaex_rice"],
    "Healthy": [],
}
GENERAL_SOURCE_IDS = ["irri_n_excess", "irri_awd"]

DISCLAIMER = {
    "en": "This is a decision-support tool, not a replacement for an agriculture expert. The result can be wrong. Confirm the diagnosis and any treatment with your local agriculture officer or Krishi Vigyan Kendra (KVK). Always follow the product label for dose, safety and waiting periods.",
    "kn": "ಇದು ನಿರ್ಧಾರ ಬೆಂಬಲ ಸಾಧನ ಮಾತ್ರ; ಕೃಷಿ ತಜ್ಞರ ಬದಲಿಯಲ್ಲ. ಫಲಿತಾಂಶ ತಪ್ಪಾಗಿರಬಹುದು. ರೋಗ ನಿರ್ಣಯ ಮತ್ತು ಯಾವುದೇ ಚಿಕಿತ್ಸೆಯನ್ನು ನಿಮ್ಮ ಸ್ಥಳೀಯ ಕೃಷಿ ಅಧಿಕಾರಿ ಅಥವಾ ಕೃಷಿ ವಿಜ್ಞಾನ ಕೇಂದ್ರ (ಕೆವಿಕೆ) ಯೊಂದಿಗೆ ಖಚಿತಪಡಿಸಿಕೊಳ್ಳಿ. ಪ್ರಮಾಣ, ಸುರಕ್ಷತೆ ಮತ್ತು ಕಾಯುವ ಅವಧಿಗೆ ಯಾವಾಗಲೂ ಉತ್ಪನ್ನದ ಲೇಬಲ್ ಅನ್ನು ಅನುಸರಿಸಿ.",
    "hi": "यह निर्णय में सहायता करने वाला उपकरण है, कृषि विशेषज्ञ का विकल्प नहीं। परिणाम गलत हो सकता है। रोग की पहचान और किसी भी उपचार की पुष्टि अपने स्थानीय कृषि अधिकारी या कृषि विज्ञान केंद्र (केवीके) से करें। मात्रा, सुरक्षा और प्रतीक्षा अवधि के लिए हमेशा उत्पाद के लेबल का पालन करें।",
}

# Added to every "chemical" list so the safety line can never be forgotten.
CHEMICAL_NOTE = {
    "en": "Doses are NOT given here. Use only products registered for rice in your area, follow the product label, and ask your local agriculture officer or KVK before spraying.",
    "kn": "ಇಲ್ಲಿ ಪ್ರಮಾಣವನ್ನು ನೀಡಲಾಗಿಲ್ಲ. ನಿಮ್ಮ ಪ್ರದೇಶದಲ್ಲಿ ಭತ್ತಕ್ಕೆ ನೋಂದಾಯಿತ ಉತ್ಪನ್ನಗಳನ್ನು ಮಾತ್ರ ಬಳಸಿ, ಉತ್ಪನ್ನದ ಲೇಬಲ್ ಅನುಸರಿಸಿ, ಸಿಂಪಡಿಸುವ ಮೊದಲು ನಿಮ್ಮ ಸ್ಥಳೀಯ ಕೃಷಿ ಅಧಿಕಾರಿ ಅಥವಾ ಕೆವಿಕೆಯನ್ನು ಕೇಳಿ.",
    "hi": "यहाँ मात्रा नहीं दी गई है। केवल अपने क्षेत्र में धान के लिए पंजीकृत उत्पाद ही उपयोग करें, उत्पाद के लेबल का पालन करें, और छिड़काव से पहले अपने स्थानीय कृषि अधिकारी या केवीके से पूछें।",
}

# ---------------------------------------------------------------------------------------------
# Growth recommendations that apply whatever the diagnosis is.
# ---------------------------------------------------------------------------------------------
COMMON = {
    "en": {
        "nutrient": [
            "Fertilise according to a soil test or your local recommendation; do not guess the amounts.",
            "Split nitrogen into several smaller doses instead of one large dose, and avoid excess. Too much nitrogen makes several rice diseases worse.",
            "Keep potassium and other nutrients in balance. Ask your local office about silicon or micronutrients if your soil is known to be deficient.",
        ],
        "water": [
            "Follow the irrigation plan for your variety and season. Avoid long dry spells, and avoid letting water run from infected fields into healthy ones.",
            "Keep the field flooded from about one week before to one week after flowering.",
            "Alternate wetting and drying (AWD) with a field water tube can save water. IRRI describes re-irrigating when the water level falls to about 15 cm below the soil surface. Ask your local extension office before using it, especially if blast is a problem.",
        ],
        "spacing": [
            "Use the seed rate or spacing recommended for your variety and season. Avoid planting too densely: a thick, humid canopy helps diseases such as sheath blight.",
        ],
        "monitoring": [
            "Walk the field every week and look at leaves, sheaths and tillers in several places, not just one plant.",
            "Take dated photos of problem spots so you can compare over days and show them to the officer.",
            "Note the weather. Warm, humid and rainy spells raise the risk of most rice diseases.",
            "If symptoms spread or you are unsure, contact your local agriculture officer or KVK.",
        ],
    },
    "kn": {
        "nutrient": [
            "ಮಣ್ಣಿನ ಪರೀಕ್ಷೆ ಅಥವಾ ನಿಮ್ಮ ಸ್ಥಳೀಯ ಶಿಫಾರಸಿನ ಪ್ರಕಾರ ಗೊಬ್ಬರ ಹಾಕಿ; ಪ್ರಮಾಣವನ್ನು ಊಹಿಸಬೇಡಿ.",
            "ಸಾರಜನಕವನ್ನು ಒಂದೇ ದೊಡ್ಡ ಕಂತಿನ ಬದಲು ಹಲವು ಸಣ್ಣ ಕಂತುಗಳಲ್ಲಿ ಹಾಕಿ, ಹೆಚ್ಚು ಹಾಕುವುದನ್ನು ತಪ್ಪಿಸಿ. ಹೆಚ್ಚು ಸಾರಜನಕ ಹಲವು ಭತ್ತದ ರೋಗಗಳನ್ನು ಹೆಚ್ಚಿಸುತ್ತದೆ.",
            "ಪೊಟ್ಯಾಶ್ ಮತ್ತು ಇತರ ಪೋಷಕಾಂಶಗಳನ್ನು ಸಮತೋಲನದಲ್ಲಿ ಇಡಿ. ನಿಮ್ಮ ಮಣ್ಣಿನಲ್ಲಿ ಸಿಲಿಕಾನ್ ಅಥವಾ ಲಘು ಪೋಷಕಾಂಶಗಳ ಕೊರತೆ ಇದ್ದರೆ ಸ್ಥಳೀಯ ಕಚೇರಿಯನ್ನು ಕೇಳಿ.",
        ],
        "water": [
            "ನಿಮ್ಮ ತಳಿ ಮತ್ತು ಋತುವಿನ ನೀರಾವರಿ ಯೋಜನೆಯನ್ನು ಅನುಸರಿಸಿ. ದೀರ್ಘ ಒಣ ಅವಧಿಗಳನ್ನು ತಪ್ಪಿಸಿ, ಮತ್ತು ರೋಗಪೀಡಿತ ಹೊಲಗಳಿಂದ ಆರೋಗ್ಯವಂತ ಹೊಲಗಳಿಗೆ ನೀರು ಹರಿಯದಂತೆ ನೋಡಿಕೊಳ್ಳಿ.",
            "ಹೂ ಬಿಡುವುದಕ್ಕೆ ಸುಮಾರು ಒಂದು ವಾರ ಮೊದಲಿನಿಂದ ಒಂದು ವಾರ ನಂತರದವರೆಗೆ ಹೊಲದಲ್ಲಿ ನೀರು ನಿಲ್ಲಿಸಿ.",
            "ಹೊಲದ ನೀರಿನ ಕೊಳವೆಯೊಂದಿಗೆ ಪರ್ಯಾಯ ನೀರು-ಒಣಗಿಸುವಿಕೆ (AWD) ನೀರನ್ನು ಉಳಿಸಬಹುದು. ನೀರಿನ ಮಟ್ಟ ಮಣ್ಣಿನ ಮೇಲ್ಮೈಗಿಂತ ಸುಮಾರು 15 ಸೆಂ.ಮೀ. ಕೆಳಗೆ ಇಳಿದಾಗ ಮತ್ತೆ ನೀರು ಹಾಯಿಸಲು IRRI ವಿವರಿಸುತ್ತದೆ. ಬಳಸುವ ಮೊದಲು, ವಿಶೇಷವಾಗಿ ಬ್ಲಾಸ್ಟ್ ಸಮಸ್ಯೆ ಇದ್ದರೆ, ಸ್ಥಳೀಯ ವಿಸ್ತರಣಾ ಕಚೇರಿಯನ್ನು ಕೇಳಿ.",
        ],
        "spacing": [
            "ನಿಮ್ಮ ತಳಿ ಮತ್ತು ಋತುವಿಗೆ ಶಿಫಾರಸು ಮಾಡಿದ ಬೀಜದ ಪ್ರಮಾಣ ಅಥವಾ ಅಂತರವನ್ನು ಬಳಸಿ. ತುಂಬಾ ದಟ್ಟವಾಗಿ ನೆಡಬೇಡಿ: ದಟ್ಟ, ತೇವದ ಬೆಳೆ ಕವಚ ಅಂಗಮಾರಿ (ಶೀತ್ ಬ್ಲೈಟ್) ಮುಂತಾದ ರೋಗಗಳಿಗೆ ಸಹಾಯ ಮಾಡುತ್ತದೆ.",
        ],
        "monitoring": [
            "ಪ್ರತಿ ವಾರ ಹೊಲದಲ್ಲಿ ನಡೆದು, ಒಂದೇ ಗಿಡವನ್ನಲ್ಲ, ಹಲವು ಸ್ಥಳಗಳಲ್ಲಿ ಎಲೆಗಳು, ಕವಚಗಳು ಮತ್ತು ಕುಡಿಗಳನ್ನು ನೋಡಿ.",
            "ಸಮಸ್ಯೆಯ ಸ್ಥಳಗಳ ದಿನಾಂಕದೊಂದಿಗಿನ ಫೋಟೋ ತೆಗೆದಿಡಿ; ಹಲವು ದಿನಗಳಲ್ಲಿ ಹೋಲಿಸಲು ಮತ್ತು ಅಧಿಕಾರಿಗೆ ತೋರಿಸಲು ಸಹಾಯವಾಗುತ್ತದೆ.",
            "ಹವಾಮಾನವನ್ನು ಗಮನಿಸಿ. ಬಿಸಿ, ತೇವ ಮತ್ತು ಮಳೆಯ ಅವಧಿಗಳು ಹೆಚ್ಚಿನ ಭತ್ತದ ರೋಗಗಳ ಅಪಾಯವನ್ನು ಹೆಚ್ಚಿಸುತ್ತವೆ.",
            "ಲಕ್ಷಣಗಳು ಹರಡಿದರೆ ಅಥವಾ ನಿಮಗೆ ಖಚಿತವಿಲ್ಲದಿದ್ದರೆ ನಿಮ್ಮ ಸ್ಥಳೀಯ ಕೃಷಿ ಅಧಿಕಾರಿ ಅಥವಾ ಕೆವಿಕೆಯನ್ನು ಸಂಪರ್ಕಿಸಿ.",
        ],
    },
    "hi": {
        "nutrient": [
            "मिट्टी की जाँच या अपने स्थानीय सुझाव के अनुसार खाद दें; मात्रा का अंदाज़ा न लगाएँ।",
            "नाइट्रोजन को एक बड़ी खुराक के बजाय कई छोटी खुराकों में दें और अधिक देने से बचें। अधिक नाइट्रोजन से धान के कई रोग बढ़ते हैं।",
            "पोटाश और अन्य पोषक तत्वों का संतुलन रखें। यदि आपकी मिट्टी में सिलिकॉन या सूक्ष्म पोषक तत्वों की कमी है तो स्थानीय कार्यालय से पूछें।",
        ],
        "water": [
            "अपनी किस्म और मौसम की सिंचाई योजना का पालन करें। लंबे सूखे दौर से बचें, और रोगग्रस्त खेतों का पानी स्वस्थ खेतों में न जाने दें।",
            "फूल आने से लगभग एक सप्ताह पहले से एक सप्ताह बाद तक खेत में पानी भरा रखें।",
            "खेत में पानी की नली के साथ वैकल्पिक गीला-सूखा (AWD) पानी बचा सकता है। IRRI के अनुसार पानी का स्तर मिट्टी की सतह से लगभग 15 सेमी नीचे जाने पर फिर सिंचाई की जाती है। इसे अपनाने से पहले, खासकर यदि ब्लास्ट की समस्या है, स्थानीय विस्तार कार्यालय से पूछें।",
        ],
        "spacing": [
            "अपनी किस्म और मौसम के लिए सुझाई गई बीज दर या दूरी रखें। बहुत घना न लगाएँ: घनी और नम फसल छतरी आवरण झुलसा (शीथ ब्लाइट) जैसे रोगों को बढ़ाती है।",
        ],
        "monitoring": [
            "हर सप्ताह खेत में घूमकर केवल एक पौधा नहीं, कई जगह पत्तियों, आवरणों और कल्लों को देखें।",
            "समस्या वाली जगहों की तारीख वाली फोटो रखें ताकि कई दिनों में तुलना कर सकें और अधिकारी को दिखा सकें।",
            "मौसम पर ध्यान दें। गर्म, नम और बरसाती दौर धान के अधिकतर रोगों का खतरा बढ़ाते हैं।",
            "यदि लक्षण फैलें या आप निश्चित न हों तो अपने स्थानीय कृषि अधिकारी या केवीके से संपर्क करें।",
        ],
    },
}

# ---------------------------------------------------------------------------------------------
# Advice by severity level. The app's severity number is experimental, so every level also says to
# judge the whole field, not one leaf.
# ---------------------------------------------------------------------------------------------
SEVERITY = {
    "en": {
        "None": ["Keep up regular monitoring and good crop care."],
        "Mild": [
            "Keep monitoring every few days to see whether it spreads.",
            "Fix the causes you can control: nitrogen, water, spacing and weeds.",
            "Chemical treatment is usually not the first step at this level. Ask your local officer whether it is needed at your crop stage.",
        ],
        "Moderate": [
            "Contact your local agriculture officer or KVK within the next few days.",
            "Check how many plants in the field show symptoms, not just this leaf.",
            "Follow the local advice on treatment and timing, and read and follow the product label.",
        ],
        "Severe": [
            "Contact your local agriculture officer or KVK as soon as possible.",
            "Do not rely only on this app: the severity here is a rough, experimental, colour-based estimate.",
            "Decide on treatment and timing together with them, and use every product exactly as its label says.",
        ],
    },
    "kn": {
        "None": ["ನಿಯಮಿತ ಪರಿಶೀಲನೆ ಮತ್ತು ಉತ್ತಮ ಬೆಳೆ ಆರೈಕೆಯನ್ನು ಮುಂದುವರಿಸಿ."],
        "Mild": [
            "ಹರಡುತ್ತದೆಯೇ ಎಂದು ನೋಡಲು ಪ್ರತಿ ಕೆಲವು ದಿನಗಳಿಗೊಮ್ಮೆ ಗಮನಿಸುತ್ತಿರಿ.",
            "ನಿಮ್ಮ ನಿಯಂತ್ರಣದಲ್ಲಿರುವ ಕಾರಣಗಳನ್ನು ಸರಿಪಡಿಸಿ: ಸಾರಜನಕ, ನೀರು, ಅಂತರ ಮತ್ತು ಕಳೆ.",
            "ಈ ಮಟ್ಟದಲ್ಲಿ ರಾಸಾಯನಿಕ ಚಿಕಿತ್ಸೆ ಸಾಮಾನ್ಯವಾಗಿ ಮೊದಲ ಹೆಜ್ಜೆಯಲ್ಲ. ನಿಮ್ಮ ಬೆಳೆ ಹಂತದಲ್ಲಿ ಅದು ಬೇಕೇ ಎಂದು ಸ್ಥಳೀಯ ಅಧಿಕಾರಿಯನ್ನು ಕೇಳಿ.",
        ],
        "Moderate": [
            "ಮುಂದಿನ ಕೆಲವು ದಿನಗಳಲ್ಲಿ ನಿಮ್ಮ ಸ್ಥಳೀಯ ಕೃಷಿ ಅಧಿಕಾರಿ ಅಥವಾ ಕೆವಿಕೆಯನ್ನು ಸಂಪರ್ಕಿಸಿ.",
            "ಈ ಎಲೆಯಲ್ಲಿ ಮಾತ್ರವಲ್ಲ, ಹೊಲದಲ್ಲಿ ಎಷ್ಟು ಗಿಡಗಳಲ್ಲಿ ಲಕ್ಷಣಗಳಿವೆ ಎಂದು ಪರಿಶೀಲಿಸಿ.",
            "ಚಿಕಿತ್ಸೆ ಮತ್ತು ಸಮಯದ ಕುರಿತು ಸ್ಥಳೀಯ ಸಲಹೆ ಅನುಸರಿಸಿ, ಉತ್ಪನ್ನದ ಲೇಬಲ್ ಓದಿ ಅನುಸರಿಸಿ.",
        ],
        "Severe": [
            "ಸಾಧ್ಯವಾದಷ್ಟು ಬೇಗ ನಿಮ್ಮ ಸ್ಥಳೀಯ ಕೃಷಿ ಅಧಿಕಾರಿ ಅಥವಾ ಕೆವಿಕೆಯನ್ನು ಸಂಪರ್ಕಿಸಿ.",
            "ಈ ಆ್ಯಪ್ ಅನ್ನು ಮಾತ್ರ ನಂಬಬೇಡಿ: ಇಲ್ಲಿನ ತೀವ್ರತೆ ಬಣ್ಣದ ಆಧಾರದ ಸ್ಥೂಲ, ಪ್ರಾಯೋಗಿಕ ಅಂದಾಜು.",
            "ಚಿಕಿತ್ಸೆ ಮತ್ತು ಸಮಯವನ್ನು ಅವರೊಂದಿಗೆ ಸೇರಿ ನಿರ್ಧರಿಸಿ, ಪ್ರತಿ ಉತ್ಪನ್ನವನ್ನು ಅದರ ಲೇಬಲ್ ಹೇಳಿದಂತೆಯೇ ಬಳಸಿ.",
        ],
    },
    "hi": {
        "None": ["नियमित निगरानी और फसल की अच्छी देखभाल जारी रखें।"],
        "Mild": [
            "हर कुछ दिन में देखते रहें कि रोग फैल तो नहीं रहा।",
            "जिन कारणों को आप नियंत्रित कर सकते हैं उन्हें सुधारें: नाइट्रोजन, पानी, दूरी और खरपतवार।",
            "इस स्तर पर रासायनिक उपचार आमतौर पर पहला कदम नहीं होता। अपनी फसल की अवस्था में इसकी ज़रूरत है या नहीं, स्थानीय अधिकारी से पूछें।",
        ],
        "Moderate": [
            "अगले कुछ दिनों में अपने स्थानीय कृषि अधिकारी या केवीके से संपर्क करें।",
            "केवल इस पत्ती को नहीं, देखें कि खेत के कितने पौधों में लक्षण हैं।",
            "उपचार और समय के बारे में स्थानीय सलाह मानें, और उत्पाद का लेबल पढ़कर उसका पालन करें।",
        ],
        "Severe": [
            "जल्द से जल्द अपने स्थानीय कृषि अधिकारी या केवीके से संपर्क करें।",
            "केवल इस ऐप पर भरोसा न करें: यहाँ की गंभीरता रंग पर आधारित मोटा, प्रायोगिक अनुमान है।",
            "उपचार और समय उनके साथ मिलकर तय करें, और हर उत्पाद का उपयोग ठीक वैसे करें जैसा उसके लेबल पर लिखा है।",
        ],
    },
}

# ---------------------------------------------------------------------------------------------
# One entry per diagnosis. Keys inside each language block are identical across languages, and the lists
# are parallel (same number of points), which tests/test_knowledge.py checks.
# ---------------------------------------------------------------------------------------------
INFO = {
    # ======================================= BLAST ===========================================
    "Blast": {
        "en": {
            "name": "Blast",
            "description": "A fungal disease (Magnaporthe oryzae) that can attack leaves, stem nodes and the neck of the panicle. It is one of the most destructive rice diseases.",
            "symptoms": [
                "Early leaf spots are white to grey-green with dark green borders.",
                "Older spots become spindle (eye) shaped, with whitish-grey centres and reddish-brown edges.",
                "Severe leaf infection can kill seedlings or young plants up to the tillering stage.",
                "The fungus can also infect stem nodes and the neck of the panicle (neck blast), which can reduce grain filling.",
            ],
            "causes": [
                "Caused by the fungus Magnaporthe oryzae (also called Pyricularia oryzae).",
                "Favoured by warm, humid weather (about 25-30 °C with relative humidity above 80%), long periods of leaf wetness and frequent rain showers.",
                "Excess nitrogen fertiliser makes the disease worse.",
                "More likely where soil moisture is low or the field is not kept flooded.",
            ],
            "cultural": [
                "Grow blast-resistant or tolerant varieties. This is described as the most practical and economical control. Ask your agriculture office which varieties suit your area.",
                "Split nitrogen into two or three smaller doses and avoid excess.",
                "Where the soil is low in silicon, silicon fertiliser can help (IRRI).",
                "Keep the field flooded where possible and avoid water stress.",
                "Where it suits your local calendar, sow early once the rains begin.",
                "Keep bunds and the field free of grasses and other weeds, and manage straw and stubble after harvest as advised locally.",
            ],
            "organic": [
                "Seed treatment with Pseudomonas fluorescens (a beneficial bacterium) is listed by TNAU as a biological option. Use a registered product as per its label.",
            ],
            "chemical": [
                "TNAU lists seed treatment with fungicides such as carbendazim, captan, thiram or tricyclazole. IRRI lists foliar sprays of triazole or strobilurin fungicides, and a spray at heading can be effective.",
            ],
            "prevention": [
                "Use clean, healthy seed and resistant varieties.",
                "Avoid dry nurseries and heavy late nitrogen.",
                "Scout fields regularly in humid weather so you can act early.",
                "Remove weeds and infected straw or stubble that can carry the fungus.",
            ],
            "nutrient": ["Apply nitrogen in split doses and avoid heavy late nitrogen."],
            "water": ["Avoid letting the field dry out: blast is favoured by low soil moisture."],
            "spacing": [],
            "monitoring": ["In humid, rainy or cool-day weather, check leaves for spindle-shaped spots every few days, and check nodes and panicle necks near heading."],
        },
        "kn": {
            "name": "ಬ್ಲಾಸ್ಟ್ ರೋಗ (Blast)",
            "description": "ಎಲೆಗಳು, ಕಾಂಡದ ಗಂಟುಗಳು ಮತ್ತು ತೆನೆಯ ಕುತ್ತಿಗೆಯ ಮೇಲೆ ದಾಳಿ ಮಾಡಬಲ್ಲ ಶಿಲೀಂಧ್ರ ರೋಗ (Magnaporthe oryzae). ಇದು ಭತ್ತದ ಅತ್ಯಂತ ವಿನಾಶಕಾರಿ ರೋಗಗಳಲ್ಲಿ ಒಂದು.",
            "symptoms": [
                "ಆರಂಭದ ಎಲೆ ಚುಕ್ಕೆಗಳು ಬಿಳಿ ಅಥವಾ ಬೂದು-ಹಸಿರು ಬಣ್ಣದಲ್ಲಿದ್ದು ಗಾಢ ಹಸಿರು ಅಂಚು ಹೊಂದಿರುತ್ತವೆ.",
                "ಹಳೆಯ ಚುಕ್ಕೆಗಳು ಕಣ್ಣಿನ (ಕದಿರಿನ) ಆಕಾರ ಪಡೆದು, ಬಿಳಿ-ಬೂದು ಮಧ್ಯಭಾಗ ಮತ್ತು ಕೆಂಪು-ಕಂದು ಅಂಚು ಹೊಂದಿರುತ್ತವೆ.",
                "ತೀವ್ರ ಎಲೆ ಸೋಂಕು ಸಸಿಗಳನ್ನು ಅಥವಾ ಕುಡಿ ಒಡೆಯುವ ಹಂತದವರೆಗಿನ ಎಳೆಯ ಗಿಡಗಳನ್ನು ಕೊಲ್ಲಬಹುದು.",
                "ಶಿಲೀಂಧ್ರವು ಕಾಂಡದ ಗಂಟುಗಳು ಮತ್ತು ತೆನೆಯ ಕುತ್ತಿಗೆಗೂ (ನೆಕ್ ಬ್ಲಾಸ್ಟ್) ಸೋಂಕು ತರಬಹುದು; ಇದರಿಂದ ಕಾಳು ತುಂಬುವಿಕೆ ಕಡಿಮೆಯಾಗಬಹುದು.",
            ],
            "causes": [
                "Magnaporthe oryzae (Pyricularia oryzae ಎಂದೂ ಕರೆಯುತ್ತಾರೆ) ಶಿಲೀಂಧ್ರದಿಂದ ಉಂಟಾಗುತ್ತದೆ.",
                "ಬಿಸಿ, ತೇವದ ಹವಾಮಾನ (ಸುಮಾರು 25-30 °C ಮತ್ತು 80% ಕ್ಕಿಂತ ಹೆಚ್ಚು ಆರ್ದ್ರತೆ), ಎಲೆಗಳು ಹೆಚ್ಚು ಕಾಲ ಒದ್ದೆಯಾಗಿರುವುದು ಮತ್ತು ಪದೇ ಪದೇ ಮಳೆ ಬರುವುದು ರೋಗಕ್ಕೆ ಅನುಕೂಲಕರ.",
                "ಹೆಚ್ಚು ಸಾರಜನಕ ಗೊಬ್ಬರ ರೋಗವನ್ನು ಹೆಚ್ಚಿಸುತ್ತದೆ.",
                "ಮಣ್ಣಿನ ತೇವಾಂಶ ಕಡಿಮೆ ಇರುವ ಅಥವಾ ಹೊಲದಲ್ಲಿ ನೀರು ನಿಲ್ಲದ ಸ್ಥಳಗಳಲ್ಲಿ ಹೆಚ್ಚು ಸಾಧ್ಯತೆ.",
            ],
            "cultural": [
                "ಬ್ಲಾಸ್ಟ್ ನಿರೋಧಕ ಅಥವಾ ಸಹಿಷ್ಣು ತಳಿಗಳನ್ನು ಬೆಳೆಯಿರಿ. ಇದು ಅತ್ಯಂತ ಪ್ರಾಯೋಗಿಕ ಮತ್ತು ಕಡಿಮೆ ವೆಚ್ಚದ ನಿಯಂತ್ರಣ ಎಂದು ವಿವರಿಸಲಾಗಿದೆ. ನಿಮ್ಮ ಪ್ರದೇಶಕ್ಕೆ ಯಾವ ತಳಿಗಳು ಸೂಕ್ತ ಎಂದು ಕೃಷಿ ಕಚೇರಿಯನ್ನು ಕೇಳಿ.",
                "ಸಾರಜನಕವನ್ನು ಎರಡು ಅಥವಾ ಮೂರು ಸಣ್ಣ ಕಂತುಗಳಲ್ಲಿ ಹಾಕಿ ಮತ್ತು ಹೆಚ್ಚು ಹಾಕುವುದನ್ನು ತಪ್ಪಿಸಿ.",
                "ಮಣ್ಣಿನಲ್ಲಿ ಸಿಲಿಕಾನ್ ಕಡಿಮೆ ಇದ್ದರೆ ಸಿಲಿಕಾನ್ ಗೊಬ್ಬರ ಸಹಾಯ ಮಾಡಬಹುದು (IRRI).",
                "ಸಾಧ್ಯವಾದರೆ ಹೊಲದಲ್ಲಿ ನೀರು ನಿಲ್ಲಿಸಿ ಮತ್ತು ನೀರಿನ ಒತ್ತಡ ತಪ್ಪಿಸಿ.",
                "ನಿಮ್ಮ ಸ್ಥಳೀಯ ಕ್ಯಾಲೆಂಡರ್‌ಗೆ ಹೊಂದುವುದಾದರೆ ಮಳೆ ಆರಂಭವಾದ ಕೂಡಲೇ ಬೇಗ ಬಿತ್ತಿ.",
                "ಬದುಗಳು ಮತ್ತು ಹೊಲದಲ್ಲಿ ಹುಲ್ಲು ಹಾಗೂ ಇತರ ಕಳೆಗಳು ಇಲ್ಲದಂತೆ ನೋಡಿಕೊಳ್ಳಿ, ಮತ್ತು ಕೊಯ್ಲಿನ ನಂತರ ಹುಲ್ಲು ಹಾಗೂ ಕೂಳೆಯನ್ನು ಸ್ಥಳೀಯ ಸಲಹೆಯಂತೆ ನಿರ್ವಹಿಸಿ.",
            ],
            "organic": [
                "ಸ್ಯೂಡೋಮೊನಾಸ್ ಫ್ಲೋರೆಸೆನ್ಸ್ (ಉಪಯುಕ್ತ ಬ್ಯಾಕ್ಟೀರಿಯಾ) ಬೀಜೋಪಚಾರವನ್ನು TNAU ಜೈವಿಕ ಆಯ್ಕೆಯಾಗಿ ಪಟ್ಟಿ ಮಾಡಿದೆ. ನೋಂದಾಯಿತ ಉತ್ಪನ್ನವನ್ನು ಅದರ ಲೇಬಲ್ ಪ್ರಕಾರ ಬಳಸಿ.",
            ],
            "chemical": [
                "TNAU ಕಾರ್ಬೆಂಡಾಜಿಮ್, ಕ್ಯಾಪ್ಟಾನ್, ಥೈರಾಮ್ ಅಥವಾ ಟ್ರೈಸೈಕ್ಲಜೋಲ್ ನಂತಹ ಶಿಲೀಂಧ್ರನಾಶಕಗಳಿಂದ ಬೀಜೋಪಚಾರವನ್ನು ಪಟ್ಟಿ ಮಾಡಿದೆ. IRRI ಟ್ರೈಅಜೋಲ್ ಅಥವಾ ಸ್ಟ್ರೋಬಿಲುರಿನ್ ಶಿಲೀಂಧ್ರನಾಶಕಗಳ ಎಲೆ ಸಿಂಪರಣೆಯನ್ನು ಪಟ್ಟಿ ಮಾಡಿದೆ; ತೆನೆ ಬರುವ ಹಂತದ ಸಿಂಪರಣೆ ಪರಿಣಾಮಕಾರಿಯಾಗಬಹುದು.",
            ],
            "prevention": [
                "ಶುದ್ಧ, ಆರೋಗ್ಯಕರ ಬೀಜ ಮತ್ತು ನಿರೋಧಕ ತಳಿಗಳನ್ನು ಬಳಸಿ.",
                "ಒಣ ಸಸಿಮಡಿ ಮತ್ತು ತಡವಾದ ಹೆಚ್ಚು ಸಾರಜನಕವನ್ನು ತಪ್ಪಿಸಿ.",
                "ತೇವದ ಹವಾಮಾನದಲ್ಲಿ ಹೊಲವನ್ನು ನಿಯಮಿತವಾಗಿ ಪರಿಶೀಲಿಸಿ, ಬೇಗ ಕ್ರಮ ಕೈಗೊಳ್ಳಬಹುದು.",
                "ಶಿಲೀಂಧ್ರವನ್ನು ಹೊತ್ತೊಯ್ಯಬಲ್ಲ ಕಳೆ ಮತ್ತು ರೋಗಪೀಡಿತ ಹುಲ್ಲು ಅಥವಾ ಕೂಳೆಯನ್ನು ತೆಗೆಯಿರಿ.",
            ],
            "nutrient": ["ಸಾರಜನಕವನ್ನು ಕಂತುಗಳಲ್ಲಿ ಹಾಕಿ ಮತ್ತು ತಡವಾಗಿ ಹೆಚ್ಚು ಸಾರಜನಕ ಹಾಕುವುದನ್ನು ತಪ್ಪಿಸಿ."],
            "water": ["ಹೊಲ ಒಣಗದಂತೆ ನೋಡಿಕೊಳ್ಳಿ: ಕಡಿಮೆ ಮಣ್ಣಿನ ತೇವಾಂಶ ಬ್ಲಾಸ್ಟ್‌ಗೆ ಅನುಕೂಲಕರ."],
            "spacing": [],
            "monitoring": ["ತೇವ, ಮಳೆ ಅಥವಾ ತಂಪಾದ ಹಗಲಿನ ಹವಾಮಾನದಲ್ಲಿ ಕದಿರಿನ ಆಕಾರದ ಚುಕ್ಕೆಗಳಿಗಾಗಿ ಪ್ರತಿ ಕೆಲವು ದಿನಗಳಿಗೊಮ್ಮೆ ಎಲೆಗಳನ್ನು ಪರೀಕ್ಷಿಸಿ, ಮತ್ತು ತೆನೆ ಬರುವ ಸಮಯದಲ್ಲಿ ಗಂಟುಗಳು ಹಾಗೂ ತೆನೆಯ ಕುತ್ತಿಗೆಯನ್ನು ನೋಡಿ."],
        },
        "hi": {
            "name": "ब्लास्ट (झोंका) रोग (Blast)",
            "description": "एक फफूंद जनित रोग (Magnaporthe oryzae) जो पत्तियों, तने की गाँठों और बाली की गर्दन पर हमला कर सकता है। यह धान के सबसे विनाशकारी रोगों में से एक है।",
            "symptoms": [
                "शुरुआती पत्ती के धब्बे सफेद से भूरे-हरे होते हैं और उनके किनारे गहरे हरे होते हैं।",
                "पुराने धब्बे तकली (आँख) के आकार के हो जाते हैं, जिनका केंद्र सफेद-भूरा और किनारे लाल-भूरे होते हैं।",
                "पत्तियों का गंभीर संक्रमण पौध या कल्ले निकलने की अवस्था तक के छोटे पौधों को मार सकता है।",
                "फफूंद तने की गाँठों और बाली की गर्दन (नेक ब्लास्ट) को भी संक्रमित कर सकती है, जिससे दाना भरना घट सकता है।",
            ],
            "causes": [
                "यह Magnaporthe oryzae (जिसे Pyricularia oryzae भी कहते हैं) फफूंद से होता है।",
                "गर्म, नम मौसम (लगभग 25-30 °C और 80% से अधिक आर्द्रता), पत्तियों का लंबे समय तक गीला रहना और बार-बार बारिश रोग के लिए अनुकूल हैं।",
                "अधिक नाइट्रोजन खाद रोग को बढ़ाती है।",
                "जहाँ मिट्टी में नमी कम हो या खेत में पानी न भरा रखा जाए, वहाँ संभावना अधिक होती है।",
            ],
            "cultural": [
                "ब्लास्ट प्रतिरोधी या सहनशील किस्में उगाएँ। इसे सबसे व्यावहारिक और किफायती नियंत्रण बताया गया है। अपने क्षेत्र के लिए कौन सी किस्में उपयुक्त हैं, कृषि कार्यालय से पूछें।",
                "नाइट्रोजन को दो या तीन छोटी खुराकों में दें और अधिक देने से बचें।",
                "जहाँ मिट्टी में सिलिकॉन कम हो, वहाँ सिलिकॉन खाद मदद कर सकती है (IRRI)।",
                "जहाँ संभव हो खेत में पानी भरा रखें और पानी की कमी से बचें।",
                "यदि आपके स्थानीय कैलेंडर के अनुकूल हो तो बारिश शुरू होते ही जल्दी बुवाई करें।",
                "मेड़ों और खेत को घास व अन्य खरपतवार से मुक्त रखें, और कटाई के बाद पुआल व ठूँठ का स्थानीय सलाह के अनुसार प्रबंधन करें।",
            ],
            "organic": [
                "स्यूडोमोनास फ्लोरेसेंस (एक लाभदायक जीवाणु) से बीज उपचार को TNAU ने जैविक विकल्प के रूप में बताया है। पंजीकृत उत्पाद का उसके लेबल के अनुसार उपयोग करें।",
            ],
            "chemical": [
                "TNAU ने कार्बेन्डाजिम, कैप्टान, थीरम या ट्राइसाइक्लाजोल जैसे फफूंदनाशकों से बीज उपचार बताया है। IRRI ने ट्रायजोल या स्ट्रोबिल्यूरिन फफूंदनाशकों का पत्तियों पर छिड़काव बताया है; बाली निकलने के समय का छिड़काव प्रभावी हो सकता है।",
            ],
            "prevention": [
                "साफ, स्वस्थ बीज और प्रतिरोधी किस्मों का उपयोग करें।",
                "सूखी नर्सरी और देर से अधिक नाइट्रोजन देने से बचें।",
                "नम मौसम में खेत की नियमित निगरानी करें ताकि जल्दी कार्रवाई हो सके।",
                "खरपतवार और संक्रमित पुआल या ठूँठ हटाएँ जो फफूंद को आगे ले जा सकते हैं।",
            ],
            "nutrient": ["नाइट्रोजन खुराकों में दें और देर से अधिक नाइट्रोजन देने से बचें।"],
            "water": ["खेत को सूखने न दें: कम मिट्टी की नमी ब्लास्ट के लिए अनुकूल है।"],
            "spacing": [],
            "monitoring": ["नम, बरसाती या दिन में ठंडे मौसम में हर कुछ दिन पत्तियों पर तकली जैसे धब्बे देखें, और बाली निकलने के समय गाँठों व बाली की गर्दन की जाँच करें।"],
        },
    },
    # ===================================== BROWN SPOT ========================================
    "Brown Spot": {
        "en": {
            "name": "Brown Spot",
            "description": "A fungal disease (Bipolaris oryzae, earlier called Helminthosporium oryzae) that causes spots on leaves and grains and is linked to poor soil fertility.",
            "symptoms": [
                "Small, dark spots on leaves grow into circular to oval spots with a light-brown to grey centre and a reddish-brown edge.",
                "On resistant varieties the spots stay small, brown and pinhead-sized.",
                "Many spots can join together and kill the whole leaf.",
                "Seedlings can show small brown spots that may distort the first leaves.",
                "Infected seed can give unfilled grains, or spotted and discoloured grains.",
            ],
            "causes": [
                "Caused by the fungus Bipolaris oryzae. It can survive in seed for years and spreads by seed and wind.",
                "Favoured by high humidity (around 86-100%), warm temperatures (roughly 16-36 °C) and leaves staying wet for many hours.",
                "Common in nutrient-poor soil, including soil low in potassium, and in fields that are not kept flooded.",
                "Excess nitrogen can make it worse.",
            ],
            "cultural": [
                "Use clean, disease-free seed and tolerant varieties where available.",
                "Correct soil fertility: use balanced fertiliser based on a soil test, with enough potassium, and avoid excess nitrogen.",
                "Keep the field properly watered. The disease is common in fields that are not flooded.",
                "Remove weeds and other grasses that can host the fungus.",
            ],
            "organic": [
                "Seed treatment with Pseudomonas fluorescens is listed by TNAU. TNAU also lists hot-water seed treatment (53-54 °C for 10-12 minutes); do this carefully and only as advised by local experts, because the wrong temperature can damage seed.",
            ],
            "chemical": [
                "TNAU lists seed treatment with fungicides such as captan or thiram, and foliar fungicides recommended locally for the crop stage.",
            ],
            "prevention": [
                "Buy certified or clean seed. Do not save seed from infected fields.",
                "Maintain soil fertility every season.",
                "Avoid water stress.",
                "Scout the field in warm, humid weather.",
            ],
            "nutrient": ["Have the soil tested. Brown spot is linked to nutrient-poor soil, especially low potassium."],
            "water": ["Do not let the field stay dry for long: the disease is common in unflooded fields."],
            "spacing": [],
            "monitoring": ["Check seedlings and lower leaves for small brown spots, and look again after humid or rainy spells."],
        },
        "kn": {
            "name": "ಕಂದು ಚುಕ್ಕೆ ರೋಗ (Brown Spot)",
            "description": "ಎಲೆಗಳು ಮತ್ತು ಕಾಳುಗಳ ಮೇಲೆ ಚುಕ್ಕೆಗಳನ್ನು ಉಂಟುಮಾಡುವ ಶಿಲೀಂಧ್ರ ರೋಗ (Bipolaris oryzae, ಮೊದಲು Helminthosporium oryzae ಎಂದು ಕರೆಯಲಾಗುತ್ತಿತ್ತು). ಇದು ಮಣ್ಣಿನ ಫಲವತ್ತತೆ ಕಡಿಮೆ ಇರುವುದಕ್ಕೆ ಸಂಬಂಧಿಸಿದೆ.",
            "symptoms": [
                "ಎಲೆಗಳ ಮೇಲಿನ ಸಣ್ಣ ಗಾಢ ಚುಕ್ಕೆಗಳು ಬೆಳೆದು, ತಿಳಿ ಕಂದು ಅಥವಾ ಬೂದು ಮಧ್ಯಭಾಗ ಮತ್ತು ಕೆಂಪು-ಕಂದು ಅಂಚಿನ ದುಂಡಗಿನ ಅಥವಾ ಅಂಡಾಕಾರದ ಚುಕ್ಕೆಗಳಾಗುತ್ತವೆ.",
                "ನಿರೋಧಕ ತಳಿಗಳಲ್ಲಿ ಚುಕ್ಕೆಗಳು ಸಣ್ಣದಾಗಿ, ಕಂದು ಬಣ್ಣದಲ್ಲಿ, ಪಿನ್ ತಲೆಯ ಗಾತ್ರದಲ್ಲಿ ಉಳಿಯುತ್ತವೆ.",
                "ಹಲವು ಚುಕ್ಕೆಗಳು ಸೇರಿ ಇಡೀ ಎಲೆಯನ್ನು ಕೊಲ್ಲಬಹುದು.",
                "ಸಸಿಗಳಲ್ಲಿ ಸಣ್ಣ ಕಂದು ಚುಕ್ಕೆಗಳು ಕಾಣಬಹುದು; ಇವು ಮೊದಲ ಎಲೆಗಳನ್ನು ವಿರೂಪಗೊಳಿಸಬಹುದು.",
                "ಸೋಂಕಿತ ಬೀಜದಿಂದ ಜೊಳ್ಳು ಕಾಳುಗಳು ಅಥವಾ ಚುಕ್ಕೆಯುಳ್ಳ, ಬಣ್ಣ ಕೆಟ್ಟ ಕಾಳುಗಳು ಉಂಟಾಗಬಹುದು.",
            ],
            "causes": [
                "Bipolaris oryzae ಶಿಲೀಂಧ್ರದಿಂದ ಉಂಟಾಗುತ್ತದೆ. ಇದು ಬೀಜದಲ್ಲಿ ವರ್ಷಗಳ ಕಾಲ ಬದುಕಬಲ್ಲದು ಮತ್ತು ಬೀಜ ಹಾಗೂ ಗಾಳಿಯ ಮೂಲಕ ಹರಡುತ್ತದೆ.",
                "ಹೆಚ್ಚು ಆರ್ದ್ರತೆ (ಸುಮಾರು 86-100%), ಬಿಸಿ ತಾಪಮಾನ (ಸುಮಾರು 16-36 °C) ಮತ್ತು ಎಲೆಗಳು ಹಲವು ಗಂಟೆ ಒದ್ದೆಯಾಗಿರುವುದು ಅನುಕೂಲಕರ.",
                "ಪೋಷಕಾಂಶ ಕಡಿಮೆ ಇರುವ ಮಣ್ಣಿನಲ್ಲಿ (ಪೊಟ್ಯಾಶ್ ಕಡಿಮೆ ಇರುವ ಮಣ್ಣು ಸೇರಿ) ಮತ್ತು ನೀರು ನಿಲ್ಲದ ಹೊಲಗಳಲ್ಲಿ ಸಾಮಾನ್ಯ.",
                "ಹೆಚ್ಚು ಸಾರಜನಕ ಇದನ್ನು ಹೆಚ್ಚಿಸಬಹುದು.",
            ],
            "cultural": [
                "ಶುದ್ಧ, ರೋಗರಹಿತ ಬೀಜ ಮತ್ತು ಲಭ್ಯವಿದ್ದಲ್ಲಿ ಸಹಿಷ್ಣು ತಳಿಗಳನ್ನು ಬಳಸಿ.",
                "ಮಣ್ಣಿನ ಫಲವತ್ತತೆಯನ್ನು ಸರಿಪಡಿಸಿ: ಮಣ್ಣಿನ ಪರೀಕ್ಷೆಯ ಆಧಾರದ ಮೇಲೆ ಸಮತೋಲಿತ ಗೊಬ್ಬರ, ಸಾಕಷ್ಟು ಪೊಟ್ಯಾಶ್ ಹಾಕಿ ಮತ್ತು ಹೆಚ್ಚು ಸಾರಜನಕ ತಪ್ಪಿಸಿ.",
                "ಹೊಲಕ್ಕೆ ಸರಿಯಾಗಿ ನೀರು ಹಾಯಿಸಿ. ನೀರು ನಿಲ್ಲದ ಹೊಲಗಳಲ್ಲಿ ರೋಗ ಸಾಮಾನ್ಯ.",
                "ಶಿಲೀಂಧ್ರಕ್ಕೆ ಆಶ್ರಯ ನೀಡಬಲ್ಲ ಕಳೆ ಮತ್ತು ಇತರ ಹುಲ್ಲುಗಳನ್ನು ತೆಗೆಯಿರಿ.",
            ],
            "organic": [
                "ಸ್ಯೂಡೋಮೊನಾಸ್ ಫ್ಲೋರೆಸೆನ್ಸ್ ಬೀಜೋಪಚಾರವನ್ನು TNAU ಪಟ್ಟಿ ಮಾಡಿದೆ. ಬಿಸಿನೀರಿನ ಬೀಜೋಪಚಾರವನ್ನೂ (53-54 °C, 10-12 ನಿಮಿಷ) TNAU ಪಟ್ಟಿ ಮಾಡಿದೆ; ತಪ್ಪು ತಾಪಮಾನ ಬೀಜಕ್ಕೆ ಹಾನಿ ಮಾಡಬಹುದಾದ್ದರಿಂದ ಇದನ್ನು ಎಚ್ಚರಿಕೆಯಿಂದ ಮತ್ತು ಸ್ಥಳೀಯ ತಜ್ಞರ ಸಲಹೆಯಂತೆ ಮಾತ್ರ ಮಾಡಿ.",
            ],
            "chemical": [
                "TNAU ಕ್ಯಾಪ್ಟಾನ್ ಅಥವಾ ಥೈರಾಮ್ ನಂತಹ ಶಿಲೀಂಧ್ರನಾಶಕಗಳ ಬೀಜೋಪಚಾರ, ಹಾಗೂ ಬೆಳೆ ಹಂತಕ್ಕೆ ಸ್ಥಳೀಯವಾಗಿ ಶಿಫಾರಸು ಮಾಡಿದ ಎಲೆ ಸಿಂಪರಣೆ ಶಿಲೀಂಧ್ರನಾಶಕಗಳನ್ನು ಪಟ್ಟಿ ಮಾಡಿದೆ.",
            ],
            "prevention": [
                "ಪ್ರಮಾಣಿತ ಅಥವಾ ಶುದ್ಧ ಬೀಜ ಖರೀದಿಸಿ. ರೋಗಪೀಡಿತ ಹೊಲಗಳಿಂದ ಬೀಜ ಉಳಿಸಬೇಡಿ.",
                "ಪ್ರತಿ ಋತುವಿನಲ್ಲೂ ಮಣ್ಣಿನ ಫಲವತ್ತತೆಯನ್ನು ಕಾಪಾಡಿ.",
                "ನೀರಿನ ಒತ್ತಡ ತಪ್ಪಿಸಿ.",
                "ಬಿಸಿ, ತೇವದ ಹವಾಮಾನದಲ್ಲಿ ಹೊಲವನ್ನು ಪರಿಶೀಲಿಸಿ.",
            ],
            "nutrient": ["ಮಣ್ಣನ್ನು ಪರೀಕ್ಷಿಸಿ. ಕಂದು ಚುಕ್ಕೆ ರೋಗ ಪೋಷಕಾಂಶ ಕಡಿಮೆ ಇರುವ ಮಣ್ಣಿಗೆ, ವಿಶೇಷವಾಗಿ ಕಡಿಮೆ ಪೊಟ್ಯಾಶ್‌ಗೆ ಸಂಬಂಧಿಸಿದೆ."],
            "water": ["ಹೊಲ ಹೆಚ್ಚು ಕಾಲ ಒಣಗಿರಲು ಬಿಡಬೇಡಿ: ನೀರು ನಿಲ್ಲದ ಹೊಲಗಳಲ್ಲಿ ರೋಗ ಸಾಮಾನ್ಯ."],
            "spacing": [],
            "monitoring": ["ಸಸಿಗಳು ಮತ್ತು ಕೆಳಗಿನ ಎಲೆಗಳಲ್ಲಿ ಸಣ್ಣ ಕಂದು ಚುಕ್ಕೆಗಳನ್ನು ಪರೀಕ್ಷಿಸಿ, ಮತ್ತು ತೇವ ಅಥವಾ ಮಳೆಯ ಅವಧಿಗಳ ನಂತರ ಮತ್ತೆ ನೋಡಿ."],
        },
        "hi": {
            "name": "भूरा धब्बा रोग (Brown Spot)",
            "description": "एक फफूंद जनित रोग (Bipolaris oryzae, पहले Helminthosporium oryzae कहलाता था) जो पत्तियों और दानों पर धब्बे बनाता है और खराब मिट्टी की उर्वरता से जुड़ा है।",
            "symptoms": [
                "पत्तियों पर छोटे गहरे धब्बे बढ़कर गोल से अंडाकार हो जाते हैं, जिनका केंद्र हल्का भूरा या धूसर और किनारा लाल-भूरा होता है।",
                "प्रतिरोधी किस्मों में धब्बे छोटे, भूरे और पिन की नोक जितने रहते हैं।",
                "कई धब्बे मिलकर पूरी पत्ती को सुखा सकते हैं।",
                "पौध में छोटे भूरे धब्बे दिख सकते हैं जो पहली पत्तियों को विकृत कर सकते हैं।",
                "संक्रमित बीज से खाली दाने, या धब्बेदार और बदरंग दाने हो सकते हैं।",
            ],
            "causes": [
                "यह Bipolaris oryzae फफूंद से होता है। यह बीज में वर्षों तक जीवित रह सकती है और बीज तथा हवा से फैलती है।",
                "अधिक आर्द्रता (लगभग 86-100%), गर्म तापमान (लगभग 16-36 °C) और पत्तियों का कई घंटे गीला रहना अनुकूल है।",
                "पोषक तत्वों की कमी वाली मिट्टी (जिसमें पोटाश कम हो) और जिन खेतों में पानी भरा नहीं रखा जाता, वहाँ आम है।",
                "अधिक नाइट्रोजन इसे बढ़ा सकती है।",
            ],
            "cultural": [
                "साफ, रोगमुक्त बीज और जहाँ उपलब्ध हो सहनशील किस्में उपयोग करें।",
                "मिट्टी की उर्वरता सुधारें: मिट्टी की जाँच के आधार पर संतुलित खाद दें, पर्याप्त पोटाश रखें और अधिक नाइट्रोजन से बचें।",
                "खेत में ठीक से पानी दें। जिन खेतों में पानी भरा नहीं रहता वहाँ रोग आम है।",
                "खरपतवार और अन्य घास हटाएँ जो फफूंद को आश्रय दे सकती हैं।",
            ],
            "organic": [
                "स्यूडोमोनास फ्लोरेसेंस से बीज उपचार को TNAU ने बताया है। TNAU ने गर्म पानी से बीज उपचार (53-54 °C पर 10-12 मिनट) भी बताया है; इसे सावधानी से और केवल स्थानीय विशेषज्ञ की सलाह से करें, क्योंकि गलत तापमान बीज को नुकसान पहुँचा सकता है।",
            ],
            "chemical": [
                "TNAU ने कैप्टान या थीरम जैसे फफूंदनाशकों से बीज उपचार, और फसल अवस्था के अनुसार स्थानीय रूप से सुझाए गए पत्तियों पर छिड़काव वाले फफूंदनाशक बताए हैं।",
            ],
            "prevention": [
                "प्रमाणित या साफ बीज खरीदें। संक्रमित खेतों से बीज न बचाएँ।",
                "हर मौसम में मिट्टी की उर्वरता बनाए रखें।",
                "पानी की कमी से बचें।",
                "गर्म, नम मौसम में खेत की निगरानी करें।",
            ],
            "nutrient": ["मिट्टी की जाँच कराएँ। भूरा धब्बा रोग पोषक तत्वों की कमी वाली मिट्टी, खासकर कम पोटाश से जुड़ा है।"],
            "water": ["खेत को लंबे समय तक सूखा न रहने दें: जिन खेतों में पानी भरा नहीं रहता वहाँ रोग आम है।"],
            "spacing": [],
            "monitoring": ["पौध और निचली पत्तियों पर छोटे भूरे धब्बे देखें, और नम या बरसाती दौर के बाद फिर देखें।"],
        },
    },
    # ======================================= TUNGRO ==========================================
    "Tungro": {
        "en": {
            "name": "Tungro",
            "description": "A viral disease caused by two viruses that are spread by green leafhoppers. There is no treatment that cures an infected plant, so protecting healthy plants matters most.",
            "symptoms": [
                "Leaves turn yellow to orange-yellow.",
                "Plants are stunted and produce fewer tillers.",
                "Grains can be sterile or only partly filled.",
                "It looks similar to nitrogen deficiency, iron toxicity or acid-soil problems, so confirm with an expert. Finding green leafhoppers on the plants supports tungro.",
            ],
            "causes": [
                "Caused by two viruses acting together, spread by green leafhoppers (Nephotettix virescens and N. malayanus). The insects prefer young plants.",
                "Risk rises when planting is staggered between neighbouring fields.",
                "Risk also rises when seedlings stay long in the nursery in tungro areas, and when infected stubble or weeds that host the virus remain between seasons.",
            ],
            "cultural": [
                "Grow tungro-resistant or leafhopper-resistant varieties. Ask your local agriculture office for the current list, because lists differ between regions and years.",
                "Plant at about the same time as your neighbours (synchronous planting). Staggered planting lets leafhopper numbers build up.",
                "After harvest, plough or harrow soon to destroy stubble, remove weeds on bunds, and where possible leave a fallow gap of about a month, or rotate with pulses or oilseeds in epidemic areas.",
                "Ask your local office about the best seedling age for your area; the sources differ. Do not leave nurseries standing for many weeks in tungro areas.",
                "Light traps can help monitor leafhopper numbers (TNAU).",
                "Avoid excess nitrogen.",
            ],
            "organic": [
                "Organic options work mainly through prevention: field sanitation, resistant varieties and timely, synchronous planting. They do not cure infected plants.",
            ],
            "chemical": [
                "Insecticides target the leafhoppers, not the virus, and do not cure infected plants. TNAU mentions spraying only when leafhopper numbers pass a local threshold (about 2 per hill in tungro areas). Decide with your local office.",
            ],
            "prevention": [
                "Use resistant varieties and plant at the same time as neighbouring fields.",
                "Destroy stubble and remove weeds soon after harvest.",
                "Watch for green leafhoppers, especially in young crops.",
                "Report suspected tungro to your local agriculture office so nearby fields can be warned.",
            ],
            "nutrient": ["Avoid excess nitrogen. Yellowing alone does not mean a nutrient problem; tungro can look the same, so do not add fertiliser blindly."],
            "water": [],
            "spacing": [],
            "monitoring": ["Look for green leafhoppers on young plants and for yellow-orange, stunted patches. Check neighbouring fields too."],
        },
        "kn": {
            "name": "ಟುಂಗ್ರೋ ರೋಗ (Tungro)",
            "description": "ಹಸಿರು ಜಿಗಿ ಹುಳುಗಳು ಹರಡುವ ಎರಡು ವೈರಸ್‌ಗಳಿಂದ ಉಂಟಾಗುವ ರೋಗ. ಸೋಂಕಿತ ಗಿಡವನ್ನು ಗುಣಪಡಿಸುವ ಚಿಕಿತ್ಸೆ ಇಲ್ಲ; ಆದ್ದರಿಂದ ಆರೋಗ್ಯವಂತ ಗಿಡಗಳನ್ನು ರಕ್ಷಿಸುವುದು ಅತ್ಯಂತ ಮುಖ್ಯ.",
            "symptoms": [
                "ಎಲೆಗಳು ಹಳದಿಯಿಂದ ಕಿತ್ತಳೆ-ಹಳದಿ ಬಣ್ಣಕ್ಕೆ ತಿರುಗುತ್ತವೆ.",
                "ಗಿಡಗಳು ಕುಂಠಿತಗೊಂಡು ಕಡಿಮೆ ಕುಡಿಗಳನ್ನು ಬಿಡುತ್ತವೆ.",
                "ಕಾಳುಗಳು ಜೊಳ್ಳಾಗಬಹುದು ಅಥವಾ ಭಾಗಶಃ ಮಾತ್ರ ತುಂಬಬಹುದು.",
                "ಇದು ಸಾರಜನಕ ಕೊರತೆ, ಕಬ್ಬಿಣದ ವಿಷತ್ವ ಅಥವಾ ಆಮ್ಲ ಮಣ್ಣಿನ ಸಮಸ್ಯೆಗಳಂತೆ ಕಾಣುತ್ತದೆ; ಆದ್ದರಿಂದ ತಜ್ಞರಿಂದ ಖಚಿತಪಡಿಸಿಕೊಳ್ಳಿ. ಗಿಡಗಳ ಮೇಲೆ ಹಸಿರು ಜಿಗಿ ಹುಳುಗಳು ಕಂಡರೆ ಟುಂಗ್ರೋ ಸಾಧ್ಯತೆ ಹೆಚ್ಚು.",
            ],
            "causes": [
                "ಹಸಿರು ಜಿಗಿ ಹುಳುಗಳು (Nephotettix virescens ಮತ್ತು N. malayanus) ಹರಡುವ, ಒಟ್ಟಿಗೆ ಕಾರ್ಯನಿರ್ವಹಿಸುವ ಎರಡು ವೈರಸ್‌ಗಳಿಂದ ಉಂಟಾಗುತ್ತದೆ. ಈ ಕೀಟಗಳು ಎಳೆಯ ಗಿಡಗಳನ್ನು ಇಷ್ಟಪಡುತ್ತವೆ.",
                "ಅಕ್ಕಪಕ್ಕದ ಹೊಲಗಳಲ್ಲಿ ನಾಟಿ ಬೇರೆ ಬೇರೆ ಸಮಯದಲ್ಲಿ ಆದಾಗ ಅಪಾಯ ಹೆಚ್ಚುತ್ತದೆ.",
                "ಟುಂಗ್ರೋ ಪ್ರದೇಶಗಳಲ್ಲಿ ಸಸಿಗಳು ಸಸಿಮಡಿಯಲ್ಲಿ ಹೆಚ್ಚು ಕಾಲ ಇದ್ದಾಗ, ಮತ್ತು ವೈರಸ್‌ಗೆ ಆಶ್ರಯ ನೀಡುವ ಸೋಂಕಿತ ಕೂಳೆ ಅಥವಾ ಕಳೆಗಳು ಋತುಗಳ ನಡುವೆ ಉಳಿದಾಗಲೂ ಅಪಾಯ ಹೆಚ್ಚುತ್ತದೆ.",
            ],
            "cultural": [
                "ಟುಂಗ್ರೋ ನಿರೋಧಕ ಅಥವಾ ಜಿಗಿ ಹುಳು ನಿರೋಧಕ ತಳಿಗಳನ್ನು ಬೆಳೆಯಿರಿ. ಪ್ರದೇಶ ಮತ್ತು ವರ್ಷಗಳ ನಡುವೆ ಪಟ್ಟಿಗಳು ಬದಲಾಗುವುದರಿಂದ ಈಗಿನ ಪಟ್ಟಿಗಾಗಿ ಸ್ಥಳೀಯ ಕೃಷಿ ಕಚೇರಿಯನ್ನು ಕೇಳಿ.",
                "ನಿಮ್ಮ ನೆರೆಹೊರೆಯ ರೈತರ ಸಮಯದಲ್ಲೇ ನಾಟಿ ಮಾಡಿ (ಏಕಕಾಲಿಕ ನಾಟಿ). ಬೇರೆ ಬೇರೆ ಸಮಯದ ನಾಟಿ ಜಿಗಿ ಹುಳುಗಳ ಸಂಖ್ಯೆ ಹೆಚ್ಚಲು ಅವಕಾಶ ನೀಡುತ್ತದೆ.",
                "ಕೊಯ್ಲಿನ ನಂತರ ಕೂಳೆಯನ್ನು ನಾಶಮಾಡಲು ಬೇಗ ಉಳುಮೆ ಅಥವಾ ಕುಂಟೆ ಹೊಡೆಯಿರಿ, ಬದುಗಳ ಮೇಲಿನ ಕಳೆ ತೆಗೆಯಿರಿ, ಸಾಧ್ಯವಾದರೆ ಸುಮಾರು ಒಂದು ತಿಂಗಳು ಹೊಲ ಖಾಲಿ ಬಿಡಿ, ಅಥವಾ ರೋಗ ಹೆಚ್ಚಿರುವ ಪ್ರದೇಶಗಳಲ್ಲಿ ಬೇಳೆ ಅಥವಾ ಎಣ್ಣೆಕಾಳು ಬೆಳೆಗಳೊಂದಿಗೆ ಬೆಳೆ ಪರಿವರ್ತನೆ ಮಾಡಿ.",
                "ನಿಮ್ಮ ಪ್ರದೇಶಕ್ಕೆ ಸಸಿಯ ಸೂಕ್ತ ವಯಸ್ಸು ಎಷ್ಟು ಎಂದು ಸ್ಥಳೀಯ ಕಚೇರಿಯನ್ನು ಕೇಳಿ; ಮೂಲಗಳಲ್ಲಿ ವ್ಯತ್ಯಾಸವಿದೆ. ಟುಂಗ್ರೋ ಪ್ರದೇಶಗಳಲ್ಲಿ ಸಸಿಮಡಿಗಳನ್ನು ಹಲವು ವಾರ ಹಾಗೆಯೇ ಬಿಡಬೇಡಿ.",
                "ಬೆಳಕಿನ ಬಲೆಗಳು ಜಿಗಿ ಹುಳುಗಳ ಸಂಖ್ಯೆಯನ್ನು ಗಮನಿಸಲು ಸಹಾಯ ಮಾಡಬಹುದು (TNAU).",
                "ಹೆಚ್ಚು ಸಾರಜನಕ ತಪ್ಪಿಸಿ.",
            ],
            "organic": [
                "ಸಾವಯವ ಆಯ್ಕೆಗಳು ಮುಖ್ಯವಾಗಿ ತಡೆಗಟ್ಟುವಿಕೆಯ ಮೂಲಕ ಕೆಲಸ ಮಾಡುತ್ತವೆ: ಹೊಲದ ನೈರ್ಮಲ್ಯ, ನಿರೋಧಕ ತಳಿಗಳು ಮತ್ತು ಸಕಾಲಿಕ ಏಕಕಾಲಿಕ ನಾಟಿ. ಅವು ಸೋಂಕಿತ ಗಿಡಗಳನ್ನು ಗುಣಪಡಿಸುವುದಿಲ್ಲ.",
            ],
            "chemical": [
                "ಕೀಟನಾಶಕಗಳು ವೈರಸ್‌ಗೆ ಅಲ್ಲ, ಜಿಗಿ ಹುಳುಗಳಿಗೆ ಗುರಿ ಮಾಡುತ್ತವೆ ಮತ್ತು ಸೋಂಕಿತ ಗಿಡಗಳನ್ನು ಗುಣಪಡಿಸುವುದಿಲ್ಲ. ಜಿಗಿ ಹುಳುಗಳ ಸಂಖ್ಯೆ ಸ್ಥಳೀಯ ಮಿತಿ ದಾಟಿದಾಗ ಮಾತ್ರ ಸಿಂಪಡಿಸಲು TNAU ಸೂಚಿಸುತ್ತದೆ (ಟುಂಗ್ರೋ ಪ್ರದೇಶಗಳಲ್ಲಿ ಪ್ರತಿ ಗುಡ್ಡೆಗೆ ಸುಮಾರು 2). ನಿಮ್ಮ ಸ್ಥಳೀಯ ಕಚೇರಿಯೊಂದಿಗೆ ನಿರ್ಧರಿಸಿ.",
            ],
            "prevention": [
                "ನಿರೋಧಕ ತಳಿಗಳನ್ನು ಬಳಸಿ ಮತ್ತು ಅಕ್ಕಪಕ್ಕದ ಹೊಲಗಳ ಸಮಯದಲ್ಲೇ ನಾಟಿ ಮಾಡಿ.",
                "ಕೊಯ್ಲಿನ ನಂತರ ಬೇಗ ಕೂಳೆಯನ್ನು ನಾಶಮಾಡಿ ಮತ್ತು ಕಳೆ ತೆಗೆಯಿರಿ.",
                "ವಿಶೇಷವಾಗಿ ಎಳೆಯ ಬೆಳೆಯಲ್ಲಿ ಹಸಿರು ಜಿಗಿ ಹುಳುಗಳ ಮೇಲೆ ಗಮನವಿಡಿ.",
                "ಟುಂಗ್ರೋ ಶಂಕೆ ಇದ್ದರೆ ಹತ್ತಿರದ ಹೊಲಗಳಿಗೆ ಎಚ್ಚರಿಕೆ ನೀಡಲು ಸ್ಥಳೀಯ ಕೃಷಿ ಕಚೇರಿಗೆ ತಿಳಿಸಿ.",
            ],
            "nutrient": ["ಹೆಚ್ಚು ಸಾರಜನಕ ತಪ್ಪಿಸಿ. ಹಳದಿಯಾಗುವುದು ಮಾತ್ರ ಪೋಷಕಾಂಶ ಸಮಸ್ಯೆ ಎಂದಲ್ಲ; ಟುಂಗ್ರೋ ಕೂಡ ಹಾಗೆಯೇ ಕಾಣಬಹುದು, ಆದ್ದರಿಂದ ಕುರುಡಾಗಿ ಗೊಬ್ಬರ ಸೇರಿಸಬೇಡಿ."],
            "water": [],
            "spacing": [],
            "monitoring": ["ಎಳೆಯ ಗಿಡಗಳ ಮೇಲೆ ಹಸಿರು ಜಿಗಿ ಹುಳುಗಳನ್ನು ಮತ್ತು ಹಳದಿ-ಕಿತ್ತಳೆ, ಕುಂಠಿತ ತೇಪೆಗಳನ್ನು ನೋಡಿ. ಅಕ್ಕಪಕ್ಕದ ಹೊಲಗಳನ್ನೂ ಪರೀಕ್ಷಿಸಿ."],
        },
        "hi": {
            "name": "टुंग्रो रोग (Tungro)",
            "description": "दो विषाणुओं से होने वाला रोग जो हरे फुदके (ग्रीन लीफहॉपर) से फैलता है। संक्रमित पौधे को ठीक करने वाला कोई उपचार नहीं है, इसलिए स्वस्थ पौधों को बचाना सबसे ज़रूरी है।",
            "symptoms": [
                "पत्तियाँ पीली से नारंगी-पीली हो जाती हैं।",
                "पौधे बौने रह जाते हैं और कल्ले कम निकलते हैं।",
                "दाने खाली या आधे भरे हो सकते हैं।",
                "यह नाइट्रोजन की कमी, लौह विषाक्तता या अम्लीय मिट्टी की समस्या जैसा दिखता है, इसलिए विशेषज्ञ से पुष्टि करें। पौधों पर हरे फुदके मिलना टुंग्रो का संकेत है।",
            ],
            "causes": [
                "यह साथ काम करने वाले दो विषाणुओं से होता है, जो हरे फुदकों (Nephotettix virescens और N. malayanus) से फैलते हैं। ये कीट छोटे पौधों को पसंद करते हैं।",
                "पड़ोसी खेतों में अलग-अलग समय पर रोपाई होने से खतरा बढ़ता है।",
                "टुंग्रो वाले क्षेत्रों में नर्सरी में पौध बहुत दिन रहने पर, और मौसमों के बीच विषाणु को आश्रय देने वाले संक्रमित ठूँठ या खरपतवार बचे रहने पर भी खतरा बढ़ता है।",
            ],
            "cultural": [
                "टुंग्रो प्रतिरोधी या फुदका प्रतिरोधी किस्में उगाएँ। सूची क्षेत्र और वर्ष के अनुसार बदलती है, इसलिए ताज़ा सूची के लिए स्थानीय कृषि कार्यालय से पूछें।",
                "लगभग अपने पड़ोसियों के साथ ही रोपाई करें (समकालिक रोपाई)। अलग-अलग समय की रोपाई से फुदकों की संख्या बढ़ने का मौका मिलता है।",
                "कटाई के बाद जल्दी जुताई या हेरो चलाकर ठूँठ नष्ट करें, मेड़ों के खरपतवार हटाएँ, और संभव हो तो लगभग एक महीने खेत खाली छोड़ें, या प्रभावित क्षेत्रों में दलहन या तिलहन के साथ फसल चक्र अपनाएँ।",
                "अपने क्षेत्र के लिए पौध की उपयुक्त उम्र स्थानीय कार्यालय से पूछें; स्रोतों में अंतर है। टुंग्रो वाले क्षेत्रों में नर्सरी को कई सप्ताह तक न छोड़ें।",
                "प्रकाश जाल फुदकों की संख्या पर नज़र रखने में मदद कर सकते हैं (TNAU)।",
                "अधिक नाइट्रोजन से बचें।",
            ],
            "organic": [
                "जैविक विकल्प मुख्यतः रोकथाम से काम करते हैं: खेत की सफाई, प्रतिरोधी किस्में और समय पर समकालिक रोपाई। ये संक्रमित पौधों को ठीक नहीं करते।",
            ],
            "chemical": [
                "कीटनाशक विषाणु पर नहीं, फुदकों पर काम करते हैं और संक्रमित पौधों को ठीक नहीं करते। TNAU केवल तब छिड़काव का उल्लेख करता है जब फुदकों की संख्या स्थानीय सीमा पार करे (टुंग्रो क्षेत्रों में लगभग 2 प्रति हिल)। अपने स्थानीय कार्यालय के साथ तय करें।",
            ],
            "prevention": [
                "प्रतिरोधी किस्में उपयोग करें और पड़ोसी खेतों के साथ ही रोपाई करें।",
                "कटाई के तुरंत बाद ठूँठ नष्ट करें और खरपतवार हटाएँ।",
                "खासकर छोटी फसल में हरे फुदकों पर नज़र रखें।",
                "टुंग्रो का संदेह हो तो स्थानीय कृषि कार्यालय को बताएँ ताकि आसपास के खेतों को सचेत किया जा सके।",
            ],
            "nutrient": ["अधिक नाइट्रोजन से बचें। केवल पीलापन पोषक तत्व की समस्या नहीं दर्शाता; टुंग्रो भी ऐसा ही दिख सकता है, इसलिए आँख मूँदकर खाद न डालें।"],
            "water": [],
            "spacing": [],
            "monitoring": ["छोटे पौधों पर हरे फुदके और पीले-नारंगी, बौने टुकड़े देखें। पड़ोसी खेत भी जाँचें।"],
        },
    },
    # ===================================== SHEATH BLIGHT =====================================
    "Sheath Blight": {
        "en": {
            "name": "Sheath Blight",
            "description": "A fungal disease (Rhizoctonia solani) that mainly attacks the leaf sheaths near the water line and can spread upward, destroying leaves and young tillers.",
            "symptoms": [
                "Small greenish-grey, oval or irregular spots on the leaf sheath near the water level.",
                "Spots grow and join; leaves age and die earlier, and young tillers can be destroyed.",
                "The loss of green leaf area reduces yield.",
            ],
            "causes": [
                "Caused by the soil-borne fungus Rhizoctonia solani, which survives in soil and plant debris.",
                "Favoured by warm, humid weather and a dense, humid canopy.",
                "High nitrogen, a high seed rate or close spacing make it worse.",
                "Weeds, and water flowing from infected fields, can spread it.",
            ],
            "cultural": [
                "Use a sensible seed rate or spacing so the canopy is not too dense.",
                "Do not over-apply nitrogen. Apply what the crop needs (IRRI).",
                "Control weeds, especially on bunds, and avoid letting irrigation water flow from infected fields to healthy ones.",
                "Deep ploughing in summer and clearing stubble and debris are listed by TNAU. IRRI also lists early drainage; ask your local office whether it suits your fields.",
                "No fully resistant variety is currently available (IRRI), so cultural management is important.",
            ],
            "organic": [
                "Adding farmyard manure or green manure encourages helpful soil microbes (TNAU).",
                "TNAU lists biological treatments with Pseudomonas fluorescens or Trichoderma for seed, seedlings or soil. Use registered products as per the label.",
            ],
            "chemical": [
                "TNAU lists foliar fungicides such as carbendazim or propiconazole when needed.",
            ],
            "prevention": [
                "Avoid dense planting and excess nitrogen.",
                "Keep bunds and fields free of weeds.",
                "Clear stubble and plant debris after harvest.",
                "Do not move water from infected fields to healthy ones.",
            ],
            "nutrient": ["Apply nitrogen according to crop need, in split doses. Excess nitrogen is a major risk factor for sheath blight."],
            "water": ["Do not let water flow from infected fields into healthy ones."],
            "spacing": ["Avoid a high seed rate or close spacing; a dense canopy favours this disease."],
            "monitoring": ["Check the lower leaf sheaths near the water line for small grey-green spots, especially in warm, humid weather."],
        },
        "kn": {
            "name": "ಕವಚ ಅಂಗಮಾರಿ ರೋಗ (Sheath Blight)",
            "description": "ನೀರಿನ ಮಟ್ಟದ ಬಳಿಯ ಎಲೆ ಕವಚಗಳ ಮೇಲೆ ಮುಖ್ಯವಾಗಿ ದಾಳಿ ಮಾಡಿ ಮೇಲಕ್ಕೆ ಹರಡಿ ಎಲೆಗಳು ಮತ್ತು ಎಳೆಯ ಕುಡಿಗಳನ್ನು ನಾಶಮಾಡಬಲ್ಲ ಶಿಲೀಂಧ್ರ ರೋಗ (Rhizoctonia solani).",
            "symptoms": [
                "ನೀರಿನ ಮಟ್ಟದ ಬಳಿಯ ಎಲೆ ಕವಚದ ಮೇಲೆ ಸಣ್ಣ ಹಸಿರು-ಬೂದು, ಅಂಡಾಕಾರದ ಅಥವಾ ಅನಿಯಮಿತ ಚುಕ್ಕೆಗಳು.",
                "ಚುಕ್ಕೆಗಳು ಬೆಳೆದು ಸೇರುತ್ತವೆ; ಎಲೆಗಳು ಬೇಗ ಮುಪ್ಪಾಗಿ ಸಾಯುತ್ತವೆ ಮತ್ತು ಎಳೆಯ ಕುಡಿಗಳು ನಾಶವಾಗಬಹುದು.",
                "ಹಸಿರು ಎಲೆಯ ಪ್ರದೇಶ ಕಡಿಮೆಯಾಗುವುದರಿಂದ ಇಳುವರಿ ಕುಸಿಯುತ್ತದೆ.",
            ],
            "causes": [
                "ಮಣ್ಣು ಮತ್ತು ಸಸ್ಯದ ಅವಶೇಷಗಳಲ್ಲಿ ಬದುಕುವ, ಮಣ್ಣಿನಿಂದ ಹರಡುವ Rhizoctonia solani ಶಿಲೀಂಧ್ರದಿಂದ ಉಂಟಾಗುತ್ತದೆ.",
                "ಬಿಸಿ, ತೇವದ ಹವಾಮಾನ ಮತ್ತು ದಟ್ಟ, ತೇವದ ಬೆಳೆ ಕವಚ ಅನುಕೂಲಕರ.",
                "ಹೆಚ್ಚು ಸಾರಜನಕ, ಹೆಚ್ಚು ಬೀಜದ ಪ್ರಮಾಣ ಅಥವಾ ಹತ್ತಿರದ ಅಂತರ ರೋಗವನ್ನು ಹೆಚ್ಚಿಸುತ್ತದೆ.",
                "ಕಳೆಗಳು ಮತ್ತು ರೋಗಪೀಡಿತ ಹೊಲಗಳಿಂದ ಹರಿಯುವ ನೀರು ಇದನ್ನು ಹರಡಬಹುದು.",
            ],
            "cultural": [
                "ಬೆಳೆ ತುಂಬಾ ದಟ್ಟವಾಗದಂತೆ ಸರಿಯಾದ ಬೀಜದ ಪ್ರಮಾಣ ಅಥವಾ ಅಂತರ ಬಳಸಿ.",
                "ಸಾರಜನಕವನ್ನು ಹೆಚ್ಚು ಹಾಕಬೇಡಿ. ಬೆಳೆಗೆ ಬೇಕಾದಷ್ಟನ್ನೇ ಹಾಕಿ (IRRI).",
                "ವಿಶೇಷವಾಗಿ ಬದುಗಳ ಮೇಲಿನ ಕಳೆ ನಿಯಂತ್ರಿಸಿ, ಮತ್ತು ರೋಗಪೀಡಿತ ಹೊಲಗಳಿಂದ ಆರೋಗ್ಯವಂತ ಹೊಲಗಳಿಗೆ ನೀರು ಹರಿಯದಂತೆ ನೋಡಿಕೊಳ್ಳಿ.",
                "ಬೇಸಿಗೆಯಲ್ಲಿ ಆಳವಾದ ಉಳುಮೆ ಮತ್ತು ಕೂಳೆ ಹಾಗೂ ಅವಶೇಷಗಳ ತೆರವನ್ನು TNAU ಪಟ್ಟಿ ಮಾಡಿದೆ. IRRI ಬೇಗ ನೀರು ಬಸಿಯುವುದನ್ನೂ ಪಟ್ಟಿ ಮಾಡಿದೆ; ಅದು ನಿಮ್ಮ ಹೊಲಗಳಿಗೆ ಹೊಂದುತ್ತದೆಯೇ ಎಂದು ಸ್ಥಳೀಯ ಕಚೇರಿಯನ್ನು ಕೇಳಿ.",
                "ಪ್ರಸ್ತುತ ಸಂಪೂರ್ಣ ನಿರೋಧಕ ತಳಿ ಲಭ್ಯವಿಲ್ಲ (IRRI); ಆದ್ದರಿಂದ ಬೇಸಾಯ ಕ್ರಮಗಳ ನಿರ್ವಹಣೆ ಮುಖ್ಯ.",
            ],
            "organic": [
                "ಕೊಟ್ಟಿಗೆ ಗೊಬ್ಬರ ಅಥವಾ ಹಸಿರೆಲೆ ಗೊಬ್ಬರ ಸೇರಿಸುವುದು ಉಪಯುಕ್ತ ಮಣ್ಣಿನ ಸೂಕ್ಷ್ಮಜೀವಿಗಳನ್ನು ಉತ್ತೇಜಿಸುತ್ತದೆ (TNAU).",
                "ಬೀಜ, ಸಸಿ ಅಥವಾ ಮಣ್ಣಿಗೆ ಸ್ಯೂಡೋಮೊನಾಸ್ ಫ್ಲೋರೆಸೆನ್ಸ್ ಅಥವಾ ಟ್ರೈಕೋಡರ್ಮಾ ಜೈವಿಕ ಚಿಕಿತ್ಸೆಗಳನ್ನು TNAU ಪಟ್ಟಿ ಮಾಡಿದೆ. ನೋಂದಾಯಿತ ಉತ್ಪನ್ನಗಳನ್ನು ಲೇಬಲ್ ಪ್ರಕಾರ ಬಳಸಿ.",
            ],
            "chemical": [
                "ಅಗತ್ಯವಿದ್ದಾಗ ಕಾರ್ಬೆಂಡಾಜಿಮ್ ಅಥವಾ ಪ್ರೊಪಿಕೊನಜೋಲ್ ನಂತಹ ಎಲೆ ಸಿಂಪರಣೆ ಶಿಲೀಂಧ್ರನಾಶಕಗಳನ್ನು TNAU ಪಟ್ಟಿ ಮಾಡಿದೆ.",
            ],
            "prevention": [
                "ದಟ್ಟ ನಾಟಿ ಮತ್ತು ಹೆಚ್ಚು ಸಾರಜನಕವನ್ನು ತಪ್ಪಿಸಿ.",
                "ಬದುಗಳು ಮತ್ತು ಹೊಲಗಳನ್ನು ಕಳೆಮುಕ್ತವಾಗಿಡಿ.",
                "ಕೊಯ್ಲಿನ ನಂತರ ಕೂಳೆ ಮತ್ತು ಸಸ್ಯದ ಅವಶೇಷಗಳನ್ನು ತೆರವುಗೊಳಿಸಿ.",
                "ರೋಗಪೀಡಿತ ಹೊಲಗಳಿಂದ ಆರೋಗ್ಯವಂತ ಹೊಲಗಳಿಗೆ ನೀರು ಹರಿಸಬೇಡಿ.",
            ],
            "nutrient": ["ಸಾರಜನಕವನ್ನು ಬೆಳೆಯ ಅಗತ್ಯದ ಪ್ರಕಾರ, ಕಂತುಗಳಲ್ಲಿ ಹಾಕಿ. ಹೆಚ್ಚು ಸಾರಜನಕ ಕವಚ ಅಂಗಮಾರಿಗೆ ಪ್ರಮುಖ ಅಪಾಯಕಾರಿ ಅಂಶ."],
            "water": ["ರೋಗಪೀಡಿತ ಹೊಲಗಳಿಂದ ಆರೋಗ್ಯವಂತ ಹೊಲಗಳಿಗೆ ನೀರು ಹರಿಯಲು ಬಿಡಬೇಡಿ."],
            "spacing": ["ಹೆಚ್ಚು ಬೀಜದ ಪ್ರಮಾಣ ಅಥವಾ ಹತ್ತಿರದ ಅಂತರ ತಪ್ಪಿಸಿ; ದಟ್ಟ ಬೆಳೆ ಕವಚ ಈ ರೋಗಕ್ಕೆ ಅನುಕೂಲಕರ."],
            "monitoring": ["ವಿಶೇಷವಾಗಿ ಬಿಸಿ, ತೇವದ ಹವಾಮಾನದಲ್ಲಿ, ನೀರಿನ ಮಟ್ಟದ ಬಳಿಯ ಕೆಳಗಿನ ಎಲೆ ಕವಚಗಳಲ್ಲಿ ಸಣ್ಣ ಬೂದು-ಹಸಿರು ಚುಕ್ಕೆಗಳನ್ನು ಪರೀಕ್ಷಿಸಿ."],
        },
        "hi": {
            "name": "आवरण झुलसा रोग (Sheath Blight)",
            "description": "एक फफूंद जनित रोग (Rhizoctonia solani) जो मुख्यतः पानी की सतह के पास पत्ती के आवरण पर हमला करता है और ऊपर की ओर फैलकर पत्तियों व छोटे कल्लों को नष्ट कर सकता है।",
            "symptoms": [
                "पानी की सतह के पास पत्ती के आवरण पर छोटे हरे-धूसर, अंडाकार या अनियमित धब्बे।",
                "धब्बे बढ़कर मिल जाते हैं; पत्तियाँ जल्दी बूढ़ी होकर सूख जाती हैं और छोटे कल्ले नष्ट हो सकते हैं।",
                "हरी पत्ती का क्षेत्र घटने से उपज कम होती है।",
            ],
            "causes": [
                "यह मिट्टी से फैलने वाली Rhizoctonia solani फफूंद से होता है, जो मिट्टी और पौधों के अवशेषों में जीवित रहती है।",
                "गर्म, नम मौसम और घनी, नम फसल छतरी अनुकूल है।",
                "अधिक नाइट्रोजन, अधिक बीज दर या पास-पास रोपाई इसे बढ़ाती है।",
                "खरपतवार और संक्रमित खेतों से बहता पानी इसे फैला सकते हैं।",
            ],
            "cultural": [
                "उचित बीज दर या दूरी रखें ताकि फसल बहुत घनी न हो।",
                "नाइट्रोजन अधिक न दें। फसल की ज़रूरत के अनुसार ही दें (IRRI)।",
                "खासकर मेड़ों पर खरपतवार नियंत्रित करें, और संक्रमित खेतों से स्वस्थ खेतों में सिंचाई का पानी न जाने दें।",
                "TNAU ने गर्मी में गहरी जुताई और ठूँठ व अवशेष साफ करना बताया है। IRRI ने जल्दी जल निकासी भी बताई है; यह आपके खेतों के लिए उपयुक्त है या नहीं, स्थानीय कार्यालय से पूछें।",
                "वर्तमान में कोई पूर्णतः प्रतिरोधी किस्म उपलब्ध नहीं है (IRRI), इसलिए खेती की पद्धतियों का प्रबंधन महत्वपूर्ण है।",
            ],
            "organic": [
                "गोबर की खाद या हरी खाद डालने से मिट्टी के लाभकारी सूक्ष्मजीवों को बढ़ावा मिलता है (TNAU)।",
                "TNAU ने बीज, पौध या मिट्टी के लिए स्यूडोमोनास फ्लोरेसेंस या ट्राइकोडर्मा से जैविक उपचार बताए हैं। पंजीकृत उत्पाद लेबल के अनुसार उपयोग करें।",
            ],
            "chemical": [
                "ज़रूरत पड़ने पर TNAU ने कार्बेन्डाजिम या प्रोपिकोनाज़ोल जैसे पत्तियों पर छिड़काव वाले फफूंदनाशक बताए हैं।",
            ],
            "prevention": [
                "घनी रोपाई और अधिक नाइट्रोजन से बचें।",
                "मेड़ और खेत खरपतवार मुक्त रखें।",
                "कटाई के बाद ठूँठ और पौधों के अवशेष साफ करें।",
                "संक्रमित खेतों का पानी स्वस्थ खेतों में न भेजें।",
            ],
            "nutrient": ["नाइट्रोजन फसल की ज़रूरत के अनुसार, खुराकों में दें। अधिक नाइट्रोजन आवरण झुलसा का प्रमुख जोखिम कारक है।"],
            "water": ["संक्रमित खेतों का पानी स्वस्थ खेतों में न बहने दें।"],
            "spacing": ["अधिक बीज दर या पास-पास रोपाई से बचें; घनी फसल छतरी इस रोग के लिए अनुकूल है।"],
            "monitoring": ["खासकर गर्म, नम मौसम में पानी की सतह के पास निचले पत्ती आवरणों पर छोटे धूसर-हरे धब्बे देखें।"],
        },
    },
    # ======================================= LEAF SMUT =======================================
    "Leaf Smut": {
        "en": {
            "name": "Leaf Smut",
            "description": "A fungal disease (Entyloma oryzae) that makes small raised black spots on leaves. It usually appears late in the season and is generally considered a minor disease. The sources for this entry are US university extension pages, not IRRI or TNAU, so check it with a local expert.",
            "symptoms": [
                "Small, raised black spots or streaks (sori) on both sides of the leaf, and sometimes on sheaths.",
                "Heavily infected leaves can turn yellow, and the leaf tips may die back.",
            ],
            "causes": [
                "Caused by the fungus Entyloma oryzae. Its spores are spread by wind.",
                "The fungus survives on diseased leaf debris in the soil.",
                "It is more common with high nitrogen and late in the season.",
            ],
            "cultural": [
                "Clear and manage crop residue at the end of the season to reduce spores.",
                "Avoid excess nitrogen.",
                "Use resistant varieties if the disease has been a problem in your fields. Rotation with non-grass crops can also help (Texas A&M).",
            ],
            "organic": [
                "No specific organic treatment was found in the sources. Good field hygiene and balanced nutrition are the main steps.",
            ],
            "chemical": [
                "Fungicides are generally not recommended for leaf smut, because it usually causes little or no yield loss (extension sources). Ask your local agriculture officer if the disease is severe in your field.",
            ],
            "prevention": [
                "Clear old leaf debris at the end of each season.",
                "Avoid excess nitrogen.",
                "Choose resistant varieties where the disease has been a problem.",
            ],
            "nutrient": ["Avoid excess nitrogen; high nitrogen increases leaf smut."],
            "water": [],
            "spacing": [],
            "monitoring": ["Check older leaves late in the season. If many leaves are yellowing and drying from the tips, show a photo to your local officer."],
        },
        "kn": {
            "name": "ಲೀಫ್ ಸ್ಮಟ್ (Leaf Smut)",
            "description": "ಎಲೆಗಳ ಮೇಲೆ ಸಣ್ಣ ಉಬ್ಬಿದ ಕಪ್ಪು ಚುಕ್ಕೆಗಳನ್ನು ಉಂಟುಮಾಡುವ ಶಿಲೀಂಧ್ರ ರೋಗ (Entyloma oryzae). ಇದು ಸಾಮಾನ್ಯವಾಗಿ ಋತುವಿನ ಕೊನೆಯಲ್ಲಿ ಕಾಣಿಸಿಕೊಳ್ಳುತ್ತದೆ ಮತ್ತು ಸಾಮಾನ್ಯವಾಗಿ ಸಣ್ಣ ರೋಗವೆಂದು ಪರಿಗಣಿಸಲಾಗುತ್ತದೆ. ಈ ವಿಭಾಗದ ಮೂಲಗಳು IRRI ಅಥವಾ TNAU ಅಲ್ಲ, ಅಮೆರಿಕದ ವಿಶ್ವವಿದ್ಯಾಲಯ ವಿಸ್ತರಣಾ ಪುಟಗಳು; ಆದ್ದರಿಂದ ಸ್ಥಳೀಯ ತಜ್ಞರೊಂದಿಗೆ ಪರಿಶೀಲಿಸಿ.",
            "symptoms": [
                "ಎಲೆಯ ಎರಡೂ ಬದಿಗಳಲ್ಲಿ, ಕೆಲವೊಮ್ಮೆ ಕವಚಗಳ ಮೇಲೆ, ಸಣ್ಣ ಉಬ್ಬಿದ ಕಪ್ಪು ಚುಕ್ಕೆಗಳು ಅಥವಾ ಗೆರೆಗಳು (ಸೋರೈ).",
                "ತೀವ್ರವಾಗಿ ಸೋಂಕಿತ ಎಲೆಗಳು ಹಳದಿಯಾಗಬಹುದು ಮತ್ತು ಎಲೆಯ ತುದಿಗಳು ಒಣಗಬಹುದು.",
            ],
            "causes": [
                "Entyloma oryzae ಶಿಲೀಂಧ್ರದಿಂದ ಉಂಟಾಗುತ್ತದೆ. ಇದರ ಬೀಜಕಗಳು ಗಾಳಿಯ ಮೂಲಕ ಹರಡುತ್ತವೆ.",
                "ಶಿಲೀಂಧ್ರವು ಮಣ್ಣಿನಲ್ಲಿರುವ ರೋಗಪೀಡಿತ ಎಲೆ ಅವಶೇಷಗಳ ಮೇಲೆ ಬದುಕುತ್ತದೆ.",
                "ಹೆಚ್ಚು ಸಾರಜನಕ ಇದ್ದಾಗ ಮತ್ತು ಋತುವಿನ ಕೊನೆಯಲ್ಲಿ ಹೆಚ್ಚು ಕಂಡುಬರುತ್ತದೆ.",
            ],
            "cultural": [
                "ಬೀಜಕಗಳನ್ನು ಕಡಿಮೆ ಮಾಡಲು ಋತುವಿನ ಕೊನೆಯಲ್ಲಿ ಬೆಳೆ ಅವಶೇಷಗಳನ್ನು ತೆರವುಗೊಳಿಸಿ ಮತ್ತು ನಿರ್ವಹಿಸಿ.",
                "ಹೆಚ್ಚು ಸಾರಜನಕ ತಪ್ಪಿಸಿ.",
                "ನಿಮ್ಮ ಹೊಲಗಳಲ್ಲಿ ರೋಗ ಸಮಸ್ಯೆಯಾಗಿದ್ದರೆ ನಿರೋಧಕ ತಳಿಗಳನ್ನು ಬಳಸಿ. ಹುಲ್ಲಲ್ಲದ ಬೆಳೆಗಳೊಂದಿಗೆ ಬೆಳೆ ಪರಿವರ್ತನೆಯೂ ಸಹಾಯ ಮಾಡಬಹುದು (Texas A&M).",
            ],
            "organic": [
                "ಮೂಲಗಳಲ್ಲಿ ನಿರ್ದಿಷ್ಟ ಸಾವಯವ ಚಿಕಿತ್ಸೆ ಕಂಡುಬಂದಿಲ್ಲ. ಉತ್ತಮ ಹೊಲದ ನೈರ್ಮಲ್ಯ ಮತ್ತು ಸಮತೋಲಿತ ಪೋಷಣೆ ಮುಖ್ಯ ಹೆಜ್ಜೆಗಳು.",
            ],
            "chemical": [
                "ಲೀಫ್ ಸ್ಮಟ್‌ಗೆ ಸಾಮಾನ್ಯವಾಗಿ ಶಿಲೀಂಧ್ರನಾಶಕಗಳನ್ನು ಶಿಫಾರಸು ಮಾಡುವುದಿಲ್ಲ, ಏಕೆಂದರೆ ಇದು ಸಾಮಾನ್ಯವಾಗಿ ಇಳುವರಿಗೆ ಕಡಿಮೆ ಅಥವಾ ಯಾವುದೇ ನಷ್ಟ ಮಾಡುವುದಿಲ್ಲ (ವಿಸ್ತರಣಾ ಮೂಲಗಳು). ನಿಮ್ಮ ಹೊಲದಲ್ಲಿ ರೋಗ ತೀವ್ರವಾಗಿದ್ದರೆ ಸ್ಥಳೀಯ ಕೃಷಿ ಅಧಿಕಾರಿಯನ್ನು ಕೇಳಿ.",
            ],
            "prevention": [
                "ಪ್ರತಿ ಋತುವಿನ ಕೊನೆಯಲ್ಲಿ ಹಳೆಯ ಎಲೆ ಅವಶೇಷಗಳನ್ನು ತೆರವುಗೊಳಿಸಿ.",
                "ಹೆಚ್ಚು ಸಾರಜನಕ ತಪ್ಪಿಸಿ.",
                "ರೋಗ ಸಮಸ್ಯೆಯಾಗಿರುವಲ್ಲಿ ನಿರೋಧಕ ತಳಿಗಳನ್ನು ಆರಿಸಿ.",
            ],
            "nutrient": ["ಹೆಚ್ಚು ಸಾರಜನಕ ತಪ್ಪಿಸಿ; ಹೆಚ್ಚು ಸಾರಜನಕ ಲೀಫ್ ಸ್ಮಟ್ ಅನ್ನು ಹೆಚ್ಚಿಸುತ್ತದೆ."],
            "water": [],
            "spacing": [],
            "monitoring": ["ಋತುವಿನ ಕೊನೆಯಲ್ಲಿ ಹಳೆಯ ಎಲೆಗಳನ್ನು ಪರೀಕ್ಷಿಸಿ. ಹಲವು ಎಲೆಗಳು ತುದಿಯಿಂದ ಹಳದಿಯಾಗಿ ಒಣಗುತ್ತಿದ್ದರೆ ಫೋಟೋವನ್ನು ಸ್ಥಳೀಯ ಅಧಿಕಾರಿಗೆ ತೋರಿಸಿ."],
        },
        "hi": {
            "name": "लीफ स्मट (पत्ती कंडुआ) (Leaf Smut)",
            "description": "एक फफूंद जनित रोग (Entyloma oryzae) जो पत्तियों पर छोटे उभरे काले धब्बे बनाता है। यह आमतौर पर मौसम के अंत में दिखता है और इसे सामान्यतः छोटा रोग माना जाता है। इस प्रविष्टि के स्रोत अमेरिकी विश्वविद्यालयों के विस्तार पृष्ठ हैं, IRRI या TNAU नहीं; इसलिए स्थानीय विशेषज्ञ से जाँच करें।",
            "symptoms": [
                "पत्ती के दोनों ओर, और कभी-कभी आवरण पर, छोटे उभरे काले धब्बे या धारियाँ (सोराई)।",
                "अधिक संक्रमित पत्तियाँ पीली हो सकती हैं और पत्ती की नोक सूख सकती है।",
            ],
            "causes": [
                "यह Entyloma oryzae फफूंद से होता है। इसके बीजाणु हवा से फैलते हैं।",
                "फफूंद मिट्टी में रोगग्रस्त पत्तियों के अवशेषों पर जीवित रहती है।",
                "अधिक नाइट्रोजन होने पर और मौसम के अंत में यह अधिक आम है।",
            ],
            "cultural": [
                "बीजाणु कम करने के लिए मौसम के अंत में फसल के अवशेष साफ करें और उनका प्रबंधन करें।",
                "अधिक नाइट्रोजन से बचें।",
                "यदि आपके खेतों में रोग की समस्या रही है तो प्रतिरोधी किस्में उपयोग करें। घास-रहित फसलों के साथ फसल चक्र भी मदद कर सकता है (Texas A&M)।",
            ],
            "organic": [
                "स्रोतों में कोई विशेष जैविक उपचार नहीं मिला। खेत की अच्छी सफाई और संतुलित पोषण मुख्य कदम हैं।",
            ],
            "chemical": [
                "लीफ स्मट के लिए फफूंदनाशक आमतौर पर अनुशंसित नहीं हैं, क्योंकि इससे आमतौर पर उपज में बहुत कम या कोई नुकसान नहीं होता (विस्तार स्रोत)। यदि आपके खेत में रोग गंभीर है तो स्थानीय कृषि अधिकारी से पूछें।",
            ],
            "prevention": [
                "हर मौसम के अंत में पुरानी पत्तियों के अवशेष साफ करें।",
                "अधिक नाइट्रोजन से बचें।",
                "जहाँ रोग की समस्या रही हो वहाँ प्रतिरोधी किस्में चुनें।",
            ],
            "nutrient": ["अधिक नाइट्रोजन से बचें; अधिक नाइट्रोजन लीफ स्मट बढ़ाती है।"],
            "water": [],
            "spacing": [],
            "monitoring": ["मौसम के अंत में पुरानी पत्तियाँ देखें। यदि कई पत्तियाँ नोक से पीली होकर सूख रही हों तो फोटो स्थानीय अधिकारी को दिखाएँ।"],
        },
    },
    # ======================================= HEALTHY =========================================
    "Healthy": {
        "en": {
            "name": "Healthy",
            "description": "The model found no sign of the diseases it knows on this leaf. A healthy-looking leaf does not guarantee that the whole plant or field is healthy: some problems start on sheaths or other plants, or show up later.",
            "symptoms": [],
            "causes": [],
            "cultural": [],
            "organic": [],
            "chemical": [],
            "prevention": [
                "Use clean, healthy seed and a variety suited to your area.",
                "Keep nitrogen balanced and split into several doses.",
                "Keep bunds and fields free of weeds, and clear stubble and debris after harvest.",
                "Keep monitoring regularly, especially after warm, humid or rainy spells.",
            ],
            "nutrient": [],
            "water": [],
            "spacing": [],
            "monitoring": ["Check several leaves from different plants, not just this one. If you see spots, yellowing or stunting, photograph them and ask your local officer."],
        },
        "kn": {
            "name": "ಆರೋಗ್ಯವಂತ (Healthy)",
            "description": "ಮಾದರಿಗೆ ತಿಳಿದಿರುವ ರೋಗಗಳ ಯಾವುದೇ ಲಕ್ಷಣ ಈ ಎಲೆಯಲ್ಲಿ ಕಂಡುಬಂದಿಲ್ಲ. ಆರೋಗ್ಯವಂತವಾಗಿ ಕಾಣುವ ಎಲೆ ಇಡೀ ಗಿಡ ಅಥವಾ ಹೊಲ ಆರೋಗ್ಯವಾಗಿದೆ ಎಂಬುದಕ್ಕೆ ಖಾತರಿಯಲ್ಲ: ಕೆಲವು ಸಮಸ್ಯೆಗಳು ಕವಚಗಳಲ್ಲಿ ಅಥವಾ ಇತರ ಗಿಡಗಳಲ್ಲಿ ಆರಂಭವಾಗುತ್ತವೆ, ಅಥವಾ ನಂತರ ಕಾಣಿಸಿಕೊಳ್ಳುತ್ತವೆ.",
            "symptoms": [],
            "causes": [],
            "cultural": [],
            "organic": [],
            "chemical": [],
            "prevention": [
                "ಶುದ್ಧ, ಆರೋಗ್ಯಕರ ಬೀಜ ಮತ್ತು ನಿಮ್ಮ ಪ್ರದೇಶಕ್ಕೆ ಸೂಕ್ತ ತಳಿಯನ್ನು ಬಳಸಿ.",
                "ಸಾರಜನಕವನ್ನು ಸಮತೋಲನದಲ್ಲಿ ಇಟ್ಟು ಹಲವು ಕಂತುಗಳಲ್ಲಿ ಹಾಕಿ.",
                "ಬದುಗಳು ಮತ್ತು ಹೊಲಗಳನ್ನು ಕಳೆಮುಕ್ತವಾಗಿಡಿ, ಕೊಯ್ಲಿನ ನಂತರ ಕೂಳೆ ಮತ್ತು ಅವಶೇಷಗಳನ್ನು ತೆರವುಗೊಳಿಸಿ.",
                "ವಿಶೇಷವಾಗಿ ಬಿಸಿ, ತೇವ ಅಥವಾ ಮಳೆಯ ಅವಧಿಗಳ ನಂತರ ನಿಯಮಿತವಾಗಿ ಗಮನಿಸುತ್ತಿರಿ.",
            ],
            "nutrient": [],
            "water": [],
            "spacing": [],
            "monitoring": ["ಇದೊಂದೇ ಅಲ್ಲ, ಬೇರೆ ಬೇರೆ ಗಿಡಗಳ ಹಲವು ಎಲೆಗಳನ್ನು ಪರೀಕ್ಷಿಸಿ. ಚುಕ್ಕೆ, ಹಳದಿ ಅಥವಾ ಕುಂಠಿತ ಕಂಡರೆ ಫೋಟೋ ತೆಗೆದು ಸ್ಥಳೀಯ ಅಧಿಕಾರಿಯನ್ನು ಕೇಳಿ."],
        },
        "hi": {
            "name": "स्वस्थ (Healthy)",
            "description": "मॉडल को इस पत्ती पर अपने ज्ञात रोगों का कोई संकेत नहीं मिला। स्वस्थ दिखने वाली पत्ती इस बात की गारंटी नहीं कि पूरा पौधा या खेत स्वस्थ है: कुछ समस्याएँ आवरण या अन्य पौधों पर शुरू होती हैं, या बाद में दिखती हैं।",
            "symptoms": [],
            "causes": [],
            "cultural": [],
            "organic": [],
            "chemical": [],
            "prevention": [
                "साफ, स्वस्थ बीज और अपने क्षेत्र के अनुकूल किस्म उपयोग करें।",
                "नाइट्रोजन संतुलित रखें और कई खुराकों में दें।",
                "मेड़ और खेत खरपतवार मुक्त रखें, और कटाई के बाद ठूँठ व अवशेष साफ करें।",
                "खासकर गर्म, नम या बरसाती दौर के बाद नियमित निगरानी जारी रखें।",
            ],
            "nutrient": [],
            "water": [],
            "spacing": [],
            "monitoring": ["केवल यह नहीं, अलग-अलग पौधों की कई पत्तियाँ जाँचें। यदि धब्बे, पीलापन या बौनापन दिखे तो फोटो लेकर स्थानीय अधिकारी से पूछें।"],
        },
    },
}

SECTION_KEYS_LISTS = ("symptoms", "causes", "cultural", "organic", "chemical", "prevention", "nutrient", "water", "spacing", "monitoring")


def known_labels() -> list[str]:
    return list(INFO)


def _lang(lang: str) -> str:
    return lang if lang in LANGS else DEFAULT_LANG


def names(lang: str) -> dict[str, str]:
    """Localised disease names by class label, e.g. {"Blast": "ಬ್ಲಾಸ್ಟ್ ರೋಗ (Blast)", ...}."""
    lang = _lang(lang)
    return {label: INFO[label][lang]["name"] for label in INFO}


def get_info(label: str, lang: str = "en", severity: str | None = None) -> dict | None:
    """Everything the app and the PDF show for one diagnosis, in one language. None if the label is unknown.

    severity: "Mild" | "Moderate" | "Severe" | None. A healthy leaf always gets the "None" advice.
    """
    if label not in INFO:
        return None
    lang = _lang(lang)
    d = INFO[label][lang]
    common = COMMON[lang]
    level = "None" if label == "Healthy" else (severity if severity in ("Mild", "Moderate", "Severe") else None)
    chemical = list(d["chemical"])
    if label != "Healthy":
        chemical.append(CHEMICAL_NOTE[lang])  # always present, never forgotten by a content edit
    return {
        "label": label,
        "lang": lang,
        "name": d["name"],
        "description": d["description"],
        "symptoms": d["symptoms"],
        "causes": d["causes"],
        "management": {"cultural": d["cultural"], "organic": d["organic"], "chemical": chemical},
        "prevention": d["prevention"],
        "growth": {key: d[key] + common[key] for key in ("nutrient", "water", "spacing", "monitoring")},
        "severity_advice": SEVERITY[lang][level] if level else [],
        "sources": [SOURCES[i] for i in SOURCE_IDS[label] + GENERAL_SOURCE_IDS],
        "disclaimer": DISCLAIMER[lang],
        "translation_reviewed": lang == "en",  # kn / hi are still AI-written drafts
    }
