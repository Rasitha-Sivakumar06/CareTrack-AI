import re


def extract_clinical_information(text: str) -> dict:
    """
    Extract common clinical measurements from medical report text.

    This is a rule-based extraction layer, not a diagnostic system.
    Temperature is stored in Celsius only when its unit is recognized.
    Missing or invalid values remain None.
    """

    result = {
        "blood_pressure": None,
        "systolic_bp": None,
        "diastolic_bp": None,
        "hemoglobin": None,
        "blood_glucose": None,
        "heart_rate": None,
        "temperature": None,
        "oxygen_saturation": None,
        "weight": None,
    }

    if not isinstance(text, str) or not text.strip():
        return result

    normalized_text = (
        text.lower()
        .replace("–", "-")
        .replace("—", "-")
        .replace("：", ":")
    )

    # BLOOD PRESSURE
    # Supports both inline formats (e.g., "BP: 130/85", "118/76 mmHg")
    # and separate lines (e.g., "Systolic blood pressure\n118\nmmHg", "Diastolic BP: 76").
    systolic = None
    diastolic = None

    # 1. Inline format with slash
    inline_bp_match = re.search(
        r"(?:\b(?:blood\s*pressure|bp)\b\s*[:\-]?\s*(\d{2,3})\s*/\s*(\d{2,3})\b|"
        r"\b(\d{2,3})\s*/\s*(\d{2,3})\s*(?:mm\s*hg)\b)",
        normalized_text,
    )
    if inline_bp_match:
        s_val = int(inline_bp_match.group(1) or inline_bp_match.group(3))
        d_val = int(inline_bp_match.group(2) or inline_bp_match.group(4))
        if 50 <= s_val <= 300:
            systolic = s_val
        if 20 <= d_val <= 150:
            diastolic = d_val

    # 2. Separate systolic line/field if not already extracted
    if systolic is None:
        sys_match = re.search(
            r"\b(?:systolic\s*(?:blood\s*pressure|bp)?|systolic)\b"
            r"\s*[:\-\s]\s*(\d{2,3})\b",
            normalized_text,
        )
        if sys_match:
            val = int(sys_match.group(1))
            if 50 <= val <= 300:
                systolic = val

    # 3. Separate diastolic line/field if not already extracted
    if diastolic is None:
        dia_match = re.search(
            r"\b(?:diastolic\s*(?:blood\s*pressure|bp)?|diastolic)\b"
            r"\s*[:\-\s]\s*(\d{2,3})\b",
            normalized_text,
        )
        if dia_match:
            val = int(dia_match.group(1))
            if 20 <= val <= 150:
                diastolic = val

    # Validate relationship and assign
    if systolic is not None and diastolic is not None:
        if systolic > diastolic:
            result["systolic_bp"] = systolic
            result["diastolic_bp"] = diastolic
            result["blood_pressure"] = f"{systolic}/{diastolic}"
        else:
            # Inverted values (systolic <= diastolic) are invalid
            result["systolic_bp"] = None
            result["diastolic_bp"] = None
            result["blood_pressure"] = None
    elif systolic is not None:
        result["systolic_bp"] = systolic
        result["diastolic_bp"] = None
        result["blood_pressure"] = None
    elif diastolic is not None:
        result["systolic_bp"] = None
        result["diastolic_bp"] = diastolic
        result["blood_pressure"] = None

    # HEMOGLOBIN
    # Examples: Hemoglobin: 13.2 g/dL, Hb: 13.2

    hemoglobin_match = re.search(
        r"\b(?:hemoglobin|haemoglobin|hb)\b"
        r"\s*[:\-]?\s*(\d{1,2}(?:\.\d+)?)",
        normalized_text,
    )

    if hemoglobin_match:
        value = float(hemoglobin_match.group(1))

        if 1 <= value <= 30:
            result["hemoglobin"] = value

    # BLOOD GLUCOSE
    # Examples: Blood Glucose: 145, Glucose: 95 mg/dL

    glucose_match = re.search(
        r"\b(?:blood\s*glucose|blood\s*sugar|glucose)\b"
        r"\s*[:\-]?\s*(\d{1,4}(?:\.\d+)?)",
        normalized_text,
    )

    if glucose_match:
        value = float(glucose_match.group(1))

        if 10 <= value <= 2000:
            result["blood_glucose"] = value

    # HEART RATE
    # Examples: Heart Rate: 78 bpm, Pulse: 82

    heart_rate_match = re.search(
        r"\b(?:heart\s*rate|pulse)\b"
        r"\s*[:\-]?\s*(\d{1,3}(?:\.\d+)?)",
        normalized_text,
    )

    if heart_rate_match:
        value = float(heart_rate_match.group(1))

        if 20 <= value <= 300:
            result["heart_rate"] = value

    # TEMPERATURE
    # Celsius is the stored unit.
    # Examples: Temp: 37 C, Temperature: 98.6 F

    temperature_match = re.search(
        r"\b(?:body\s*temperature|temperature|temp)\b"
        r"\s*[:\-]?\s*"
        r"(\d{2,3}(?:\.\d+)?)\s*"
        r"(°\s*[cf]|degrees?\s*[cf]\b|[cf]\b)",
        normalized_text,
    )

    if temperature_match:
        value = float(temperature_match.group(1))
        unit = temperature_match.group(2).lower()
        unit = unit.replace(" ", "").replace("°", "")

        if unit.endswith("f"):
            value = (value - 32) * 5 / 9
        elif not unit.endswith("c"):
            value = None

        if value is not None and 25 <= value <= 45:
            result["temperature"] = round(value, 2)

    # OXYGEN SATURATION
    # Examples: SpO2: 98%, Oxygen Saturation: 97

    oxygen_match = re.search(
        r"\b(?:spo2|oxygen\s*saturation|oxygen\s*level)\b"
        r"\s*[:\-]?\s*(\d{1,3}(?:\.\d+)?)\s*%?",
        normalized_text,
    )

    if oxygen_match:
        value = float(oxygen_match.group(1))

        if 0 <= value <= 100:
            result["oxygen_saturation"] = value

    # WEIGHT
    # Examples: Weight: 68 kg, Weight: 68.5 kg

    weight_match = re.search(
        r"\bweight\b\s*[:\-]?\s*"
        r"(\d{1,3}(?:\.\d+)?)"
        r"\s*(kg|kgs|kilograms?)?\b",
        normalized_text,
    )

    if weight_match:
        value = float(weight_match.group(1))

        if 1 <= value <= 500:
            result["weight"] = value

    return result
