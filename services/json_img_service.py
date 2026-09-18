import base64
import json
import os
import re
import sys

import openai
import pypdfium2 as pdfium
from dotenv import load_dotenv
from pdf2image import convert_from_path

from config import settings

load_dotenv()


PROMPT = """You are analyzing an image of a document page.

FIRST, determine if this image contains a VISUAL org chart, flowchart, hierarchy diagram, or process flow diagram (with boxes/shapes/nodes and connecting lines or arrows).

- If the image contains ONLY plain text, bullet points, text descriptions, tables, or document paragraphs WITHOUT a visual flowchart or org chart diagram (boxes with connecting lines), set "has_diagram": false.

- If the image DOES contain a visual org chart, flowchart, or hierarchy diagram, set "has_diagram": true.

Return ONLY valid JSON (no markdown fences, no commentary) in this exact shape:

{
  "has_diagram": true,
  "chart_name": "<heading or section title of the chart/flowchart appearing above or at the top of the diagram>",
  "bounding_box": [ymin, xmin, ymax, xmax],
  "tree": {
    "name": "<root box text>",
    "children": [
      {
        "name": "<box text>",
        "children": [ ... ]
      }
    ]
  }
}

Rules when "has_diagram" is true:
- "bounding_box": [ymin, xmin, ymax, xmax] in 0 to 1000 scale. Cover ONLY the visual org chart / flowchart diagram and its section title heading right above it. EXCLUDE any body text paragraphs, bullet points, header banners, or document descriptions below or around the chart.
- Identify the exact heading or title appearing above or right before the chart for "chart_name". If no heading is present, use the top root box name.
- Reconstruct the exact hierarchy shown by the connecting lines between boxes.
- Preserve the exact text in each box, including footnote markers like * or diamond symbols.

If "has_diagram" is false, return ONLY:
{
  "has_diagram": false
}
"""


def sanitize_filename(name):
    if not name:
        return "chart"
    first_line = str(name).split("\n")[0].strip()
    cleaned = re.sub(r'[^\w\s-]', '', first_line)
    cleaned = re.sub(r'[\s-]+', '_', cleaned).strip('_').lower()
    if not cleaned:
        cleaned = "chart"
    return cleaned[:60]


def crop_image_to_bbox(image_path, bounding_box):
    if not bounding_box or not isinstance(bounding_box, list) or len(bounding_box) != 4:
        return False
    try:
        from PIL import Image
        ymin, xmin, ymax, xmax = bounding_box
        with Image.open(image_path) as img:
            w, h = img.size
            left = max(0, int(xmin * w / 1000.0) - 10)
            top = max(0, int(ymin * h / 1000.0) - 10)
            right = min(w, int(xmax * w / 1000.0) + 10)
            bottom = min(h, int(ymax * h / 1000.0) + 10)

            if right > left + 30 and bottom > top + 30:
                cropped = img.crop((left, top, right, bottom))
                cropped.save(image_path, "PNG")
                print(f"Cropped image to chart diagram region: {image_path}")
                return True
    except Exception as e:
        print(f"Warning: Failed to crop image {image_path}: {e}")
    return False


def image_to_base64(image_path):
    ext = os.path.splitext(image_path)[1].lower().lstrip(".")
    media_type = "image/png" if ext == "png" else f"image/{ext}"
    if ext in ("jpg", "jpeg"):
        media_type = "image/jpeg"
    with open(image_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    return data, media_type


def pdf_to_images(pdf_path, output_dir="images", dpi=300, filename_prefix=None):
    os.makedirs(output_dir, exist_ok=True)

    pdf_filename = os.path.splitext(os.path.basename(pdf_path))[0]

    if filename_prefix:
        image_prefix = filename_prefix
    else:
        image_prefix = pdf_filename
    try:
        pdf = pdfium.PdfDocument(pdf_path)
        paths = []
        scale = dpi / 72.0
        try:
            for i, page in enumerate(pdf):
                image = page.render(scale=scale).to_pil()
                path = os.path.join(output_dir, f"{pdf_filename}_page{i+1}.png")
                image.save(path, "PNG")
                image.close()
                paths.append(path)
        finally:
            pdf.close()
        return paths
    except Exception:
        pages = convert_from_path(pdf_path, dpi=dpi)
        paths = []
        for i, page in enumerate(pages):
            path = os.path.join(output_dir, f"{pdf_filename}_page{i+1}.png")
            page.save(path, "PNG")
            page.close()
            paths.append(path)
        return paths


def parse_chart_response(raw_text):
    if not raw_text or not raw_text.strip():
        return None, None, None

    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except Exception:
                data = {"raw_text": raw_text}
        else:
            data = {"raw_text": raw_text}

    if isinstance(data, dict):
        if data.get("has_diagram") is False:
            return None, None, None

        bounding_box = data.get("bounding_box")

        if "tree" in data:
            tree = data["tree"]
            chart_name = data.get("chart_name") or (tree.get("name") if isinstance(tree, dict) else None)
        elif "name" in data:
            tree = data
            chart_name = data.get("chart_name") or data.get("name")
        elif "raw_text" in data:
            return data, None, None
        else:
            tree = data
            chart_name = data.get("chart_name")

        return tree, chart_name, bounding_box

    return {"raw_text": raw_text}, None, None


def extract_tree_from_image_openai(image_path, client, model=None):
    b64_data, media_type = image_to_base64(image_path)

    target_model = settings.openai_model2

    try:
        print(f"Trying OpenAI model: '{target_model}'...")

        response = client.responses.create(
            model=target_model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_image",
                            "image_url": f"data:{media_type};base64,{b64_data}",
                        },
                        {
                            "type": "input_text",
                            "text": PROMPT,
                        },
                    ],
                }
            ],
        )

        raw_text = response.output_text

        tree, chart_name, bounding_box = parse_chart_response(raw_text)

        if tree is not None:
            print(
                f"Successfully processed using OpenAI model "
                f"'{target_model}'."
            )
            return tree, chart_name, bounding_box

        print(
            f"Model '{target_model}' returned no valid diagram result."
        )

    except Exception as e:
        print(
            f"OpenAI model '{target_model}' failed: {e}"
        )

    return None, None, None


def print_tree(node, prefix="", is_last=True, is_root=True):
    if is_root:
        print(node["name"])
    else:
        connector = "└── " if is_last else "├── "
        print(prefix + connector + node["name"])
    child_prefix = prefix if is_root else prefix + ("    " if is_last else "│   ")
    children = node.get("children", [])
    for i, child in enumerate(children):
        print_tree(child, child_prefix, i == len(children) - 1, is_root=False)


def main():
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")

    if len(sys.argv) < 2:
        print("Usage: python chart_to_json_ai.py <input.pdf|input.png> [optional_output.json]")
        sys.exit(1)

    input_path = sys.argv[1]
    explicit_output = sys.argv[2] if len(sys.argv) >= 3 else None

    json_dir = "json"
    os.makedirs(json_dir, exist_ok=True)

    openai_key = getattr(settings, "openai_api_key2", None) or settings.openai_api_key
    if not openai_key:
        print("ERROR: No valid API key found. Please set OPENAI_API_KEY in your .env file.")
        sys.exit(1)

    client = openai.OpenAI(api_key=openai_key)

    model = getattr(settings, "openai_model2", None) or settings.openai_model

    ext = os.path.splitext(input_path)[1].lower()
    if ext == ".pdf":
        image_paths = pdf_to_images(input_path, output_dir="images")
        print(f"Converted PDF to {len(image_paths)} page image(s) saved in 'images/'.")
    else:
        image_paths = [input_path]

    saved_json_files = []

    for idx, img_path in enumerate(image_paths):
        page_num = idx + 1
        print(f"\n--- Analyzing Page {page_num}/{len(image_paths)}: {img_path} ---")

        tree, chart_name, bounding_box = extract_tree_from_image_openai(img_path, client, model=model)

        if tree is None:
            print(f"[Skipped] Page {page_num}: No visual org chart or flowchart diagram found.")
            if ext == ".pdf" and os.path.exists(img_path):
                try:
                    os.remove(img_path)
                except Exception:
                    pass
            continue

        # Crop image file to chart diagram region (removing surrounding paragraphs/bullet points)
        if bounding_box:
            crop_image_to_bbox(img_path, bounding_box)

        if explicit_output:
            if len(image_paths) == 1:
                filename = os.path.basename(explicit_output)
            else:
                out_base, out_ext = os.path.splitext(os.path.basename(explicit_output))
                if not out_ext:
                    out_ext = ".json"
                filename = f"{out_base}_page{page_num}{out_ext}"
        else:
            clean_title = sanitize_filename(chart_name or f"chart_page{page_num}")
            filename = f"{clean_title}.json"

        target_path = os.path.join(json_dir, filename)

        # Handle filename collisions
        counter = 1
        base_target = target_path[:-5]
        while target_path in saved_json_files or os.path.exists(target_path):
            target_path = f"{base_target}_{counter}.json"
            counter += 1

        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(tree, f, indent=2)

        # Align image filename in images/ with target JSON filename
        image_base_name = os.path.splitext(os.path.basename(target_path))[0]
        final_image_path = os.path.join("images", f"{image_base_name}.png")
        if img_path != final_image_path and os.path.exists(img_path):
            try:
                if os.path.exists(final_image_path):
                    os.remove(final_image_path)
                os.rename(img_path, final_image_path)
            except Exception:
                final_image_path = img_path

        saved_json_files.append(target_path)
        print(f"Diagram Found! Title: '{chart_name}'")
        print(f"Saved tree JSON to {target_path}")
        print(f"Saved cropped chart image to {final_image_path}")
        print("Preview:\n")
        print_tree(tree)

    print(f"\nSuccessfully processed all {len(image_paths)} page(s). Created {len(saved_json_files)} chart JSON file(s) in '{json_dir}/'.")


if __name__ == "__main__":
    main()