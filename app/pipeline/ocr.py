"""
ocr.py — Step 2 of the pipeline
---------------------------------
Handles scanned PDFs and images using Tesseract OCR + OpenCV preprocessing.

The pipeline for each page:
  1. Convert PDF page to image (pdf2image)
  2. Preprocess image with OpenCV:
       - Convert to grayscale
       - Increase contrast
       - Remove noise
       - Fix skew (deskew)
  3. Run Tesseract OCR
  4. Collect text + confidence scores

Why preprocessing matters:
  A scanned certificate photographed at an angle on a phone camera might
  be blurry, skewed, and low-contrast. Tesseract struggles with this.
  OpenCV fixes these issues BEFORE Tesseract reads the image, significantly
  improving accuracy.

Usage:
  from app.pipeline.ocr import ocr_file
  result = ocr_file("scanned_certificate.jpg")
  print(result["text"])
  print(result["confidence"])  # 0-100
"""

import os
import sys
import numpy as np
from pathlib import Path

# OpenCV for image preprocessing
import cv2

# Tesseract via Python wrapper
import pytesseract
from pytesseract import Output

# Pillow for image loading
from PIL import Image

import fitz  # PyMuPDF 


# ── Tesseract language config ──────────────────────────────────────────────────
# Add Indian language codes here. Each needs the tesseract language pack installed.
# Install: sudo apt install tesseract-ocr-hin tesseract-ocr-tam tesseract-ocr-tel
# "eng" = English, "hin" = Hindi, "tam" = Tamil, "tel" = Telugu
TESSERACT_LANGUAGES = "eng+hin"  # add "+tam+tel" etc. as needed

# Tesseract config: --psm 3 = automatic page segmentation (best for full pages)
# --oem 3 = use LSTM neural network (most accurate in Tesseract 5)
TESSERACT_CONFIG = "--psm 3 --oem 3"

# If Tesseract is not on your PATH (common on Windows), set the full path here:
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\m.jayakumaran\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"


# ── Image types that can be OCR'd directly ────────────────────────────────────
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
PDF_EXTENSION    = ".pdf"


# ── Main OCR function ──────────────────────────────────────────────────────────

def ocr_file(file_path: str) -> dict:
    """
    Run OCR on a file (image or scanned PDF).

    Args:
        file_path: Path to the image or PDF file

    Returns:
        A dictionary with:
          - text:       Extracted text (string)
          - confidence: Average OCR confidence 0-100 (float)
          - pages:      Number of pages processed (int)
          - warnings:   List of warning strings (list)
    """
    ext = Path(file_path).suffix.lower()
    all_text  = []
    all_confs = []
    warnings  = []

    # ── PDF: convert each page to an image first ──────────────────────────────
    if ext == PDF_EXTENSION:
        print(f"[ocr] Converting PDF to images via PyMuPDF: {file_path}")
        try:
            doc = fitz.open(file_path)
            pages = list(doc)
            print(f"[ocr] PDF has {len(pages)} page(s)")
        except Exception as e:
            return {
                "text": "",
                "confidence": 0,
                "pages": 0,
                "warnings": [f"PDF open failed: {e}"],
            }

        for page_num, page in enumerate(pages, start=1):
            print(f"[ocr] Processing page {page_num}/{len(pages)}...")
            # Render page to image at 300 DPI using PyMuPDF (no poppler needed)
            mat = fitz.Matrix(300 / 72, 300 / 72)  # 300 DPI scale matrix
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
            pil_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            text, conf = _ocr_pil_image(pil_image, page_num)
            all_text.append(f"--- Page {page_num} ---\n{text}")
            all_confs.append(conf)
            if conf < 60:
                warnings.append(f"Page {page_num}: low OCR confidence ({conf:.0f}%)")

        doc.close()

    # ── Image: OCR directly ───────────────────────────────────────────────────
    elif ext in IMAGE_EXTENSIONS:
        print(f"[ocr] Processing image file: {file_path}")
        pil_image = Image.open(file_path)
        text, conf = _ocr_pil_image(pil_image, page_num=1)
        all_text.append(text)
        all_confs.append(conf)
        if conf < 60:
            warnings.append(f"Low OCR confidence ({conf:.0f}%) — "
                            "image may be blurry or low resolution")
    else:
        return {
            "text": "",
            "confidence": 0,
            "pages": 0,
            "warnings": [f"Unsupported file type for OCR: {ext}"],
        }

    avg_confidence = sum(all_confs) / len(all_confs) if all_confs else 0
    full_text      = "\n\n".join(all_text)

    print(f"[ocr] Done. Avg confidence: {avg_confidence:.1f}% | "
          f"Characters: {len(full_text)}")

    return {
        "text":       full_text,
        "confidence": avg_confidence,
        "pages":      len(all_text),
        "warnings":   warnings,
    }


# ── Core OCR on a single PIL image ────────────────────────────────────────────

def _ocr_pil_image(pil_image: Image.Image, page_num: int) -> tuple:
    """
    Run OCR on a single PIL image.

    Returns:
        (text: str, confidence: float)
    """
    # Convert PIL Image to OpenCV format (numpy array)
    cv_image = _pil_to_cv(pil_image)

    # Preprocess the image to improve OCR accuracy
    processed = _preprocess_image(cv_image)

    # Convert back to PIL for pytesseract
    pil_processed = Image.fromarray(processed)

    # Run Tesseract and get word-level data including confidence scores
    try:
        ocr_data = pytesseract.image_to_data(
            pil_processed,
            lang=TESSERACT_LANGUAGES,
            config=TESSERACT_CONFIG,
            output_type=Output.DICT,
        )
    except Exception as e:
        print(f"[ocr] Tesseract error on page {page_num}: {e}")
        return "", 0

    # ── Extract text and confidence ────────────────────────────────────────────
    words       = []
    confidences = []

    for i, word in enumerate(ocr_data["text"]):
        conf = int(ocr_data["conf"][i])

        # Tesseract returns -1 confidence for non-text elements — skip those
        if conf == -1:
            continue

        # Only include words with reasonable confidence
        # Words below 30% confidence are usually garbage characters
        if conf >= 30 and word.strip():
            words.append(word)
            confidences.append(conf)

    text = " ".join(words)
    avg_conf = sum(confidences) / len(confidences) if confidences else 0

    return text, avg_conf


# ── OpenCV image preprocessing ────────────────────────────────────────────────

def _preprocess_image(cv_image: np.ndarray) -> np.ndarray:
    """
    Apply a series of image processing steps to improve OCR accuracy.

    Steps applied in order:
    1. Convert to grayscale    — removes colour noise
    2. Upscale if too small    — Tesseract needs ≥300 DPI for best results
    3. Deskew                  — straightens rotated/tilted pages
    4. Denoise                 — removes scanner speckle
    5. Threshold               — converts to pure black/white

    Args:
        cv_image: OpenCV image in BGR or grayscale

    Returns:
        Processed grayscale image ready for Tesseract
    """
    # Step 1: Grayscale
    if len(cv_image.shape) == 3:
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = cv_image.copy()

    # Step 2: Upscale if image is small (less than 1000px wide)
    # Small images give Tesseract too little detail to work with
    height, width = gray.shape
    if width < 1000:
        scale_factor = 1500 / width  # scale up to at least 1500px wide
        new_width  = int(width  * scale_factor)
        new_height = int(height * scale_factor)
        gray = cv2.resize(gray, (new_width, new_height),
                          interpolation=cv2.INTER_CUBIC)
        print(f"[ocr] Upscaled image from {width}px to {new_width}px")

    # Step 3: Deskew — correct page tilt
    # Scanned pages are often slightly tilted (1-5 degrees)
    gray = _deskew(gray)

    # Step 4: Denoise — remove scanner dots and speckle
    # h=10 is a good balance: removes noise without blurring text
    denoised = cv2.fastNlMeansDenoising(gray, h=10)

    # Step 5: Adaptive threshold — convert to pure black and white
    # This handles uneven lighting across the page (common in photographed docs)
    # blockSize=11: neighbourhood size for threshold calculation
    # C=2: constant subtracted from mean (fine-tune if text is too light/dark)
    binary = cv2.adaptiveThreshold(
        denoised,
        maxValue=255,
        adaptiveMethod=cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        thresholdType=cv2.THRESH_BINARY,
        blockSize=11,
        C=2,
    )

    return binary


def _deskew(image: np.ndarray) -> np.ndarray:
    """
    Detect and correct page tilt (skew) in a grayscale image.

    How it works:
      1. Find all dark pixels (text) using threshold
      2. Calculate the angle they form using OpenCV's minAreaRect
      3. Rotate the image to correct the angle
    """
    try:
        # Find dark pixels — these are likely text
        thresh = cv2.threshold(
            image, 0, 255,
            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )[1]

        # Get coordinates of all dark (text) pixels
        coords = np.column_stack(np.where(thresh > 0))

        if len(coords) < 100:
            # Not enough text pixels to estimate skew — skip
            return image

        # Find the minimum bounding rectangle around all text pixels
        angle = cv2.minAreaRect(coords)[-1]

        # minAreaRect returns angles in [-90, 0)
        # We need to convert to a sensible rotation angle
        if angle < -45:
            angle = 90 + angle
        else:
            angle = angle

        # Only deskew if tilt is meaningful (>0.5°) and not extreme (>15°)
        # Extreme angles usually mean the page was intentionally rotated
        if abs(angle) > 0.5 and abs(angle) < 15:
            print(f"[ocr] Correcting skew angle: {angle:.2f}°")
            h, w = image.shape
            centre = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(centre, angle, 1.0)
            # BORDER_REPLICATE fills the new edges with the nearest pixel colour
            image = cv2.warpAffine(
                image, M, (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE,
            )

    except Exception as e:
        # Deskew is not critical — if it fails, just return the original
        print(f"[ocr] Deskew failed (non-critical): {e}")

    return image


def _pil_to_cv(pil_image: Image.Image) -> np.ndarray:
    """Convert a PIL Image to an OpenCV numpy array."""
    # PIL uses RGB, OpenCV uses BGR — convert colour channels
    if pil_image.mode == "RGB":
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    elif pil_image.mode == "RGBA":
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGBA2BGR)
    elif pil_image.mode == "L":
        return np.array(pil_image)  # Already grayscale
    else:
        # Convert to RGB first then to BGR
        return cv2.cvtColor(np.array(pil_image.convert("RGB")), cv2.COLOR_RGB2BGR)


# ── Quick test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m app.pipeline.ocr <image-or-pdf>")
        sys.exit(1)

    file_path = sys.argv[1]
    print(f"\nRunning OCR on: {file_path}\n{'─' * 50}")
    result = ocr_file(file_path)

    print(f"\nConfidence: {result['confidence']:.1f}%")
    print(f"Pages:      {result['pages']}")
    print(f"Warnings:   {result['warnings'] or 'none'}")
    print(f"\n── Extracted text (first 1000 chars) ──\n")
    print(result["text"][:1000])