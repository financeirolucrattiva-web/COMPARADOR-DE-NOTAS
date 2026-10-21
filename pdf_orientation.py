"""Normalize text direction in memory; never rewrite the uploaded PDF."""
from collections import Counter
from contextlib import contextmanager
from io import BytesIO
from math import atan2, degrees

import pdfplumber


@contextmanager
def readable_pdf(stream):
    original = pdfplumber.open(stream)
    corrected = None
    try:
        if len(original.pages) > 200:
            raise ValueError('Limite de 200 páginas por arquivo.')
        corrections = {}
        for index, page in enumerate(original.pages):
            directions = Counter()
            for char in page.chars:
                if not char.get('text', '').strip():
                    continue
                a, b = char['matrix'][:2]
                angle = degrees(atan2(b, a)) % 360
                nearest = (round(angle / 90) * 90) % 360
                if abs((angle - nearest + 180) % 360 - 180) < 8:
                    directions[nearest] += 1
            if directions:
                angle, count = directions.most_common(1)[0]
                if angle and count / sum(directions.values()) >= .65:
                    corrections[index] = angle
            page.close()
        if not corrections:
            yield original
            return
        import pypdfium2 as pdfium
        stream.seek(0)
        output = BytesIO()
        with pdfium.PdfDocument(stream.read()) as document:
            for index, angle in corrections.items():
                page = document[index]
                try:
                    page.set_rotation((page.get_rotation() + angle) % 360)
                finally:
                    page.close()
            document.save(output)
        output.seek(0)
        corrected = pdfplumber.open(output)
        yield corrected
    finally:
        if corrected is not None:
            corrected.close()
        original.close()
