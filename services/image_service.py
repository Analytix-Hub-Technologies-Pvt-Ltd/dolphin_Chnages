import json
from pathlib import Path


class ImageService:

    def __init__(self):
        self.image_dir = Path("storage/image_json")

        print(f"[IMAGE] image_dir={self.image_dir.resolve()}")

    def get_images_by_topic_code(self, topic_code: str):

        try:

            print(f"[IMAGE] topic_code={topic_code}")

            file_path = self.image_dir / f"{topic_code}.json"

            print(f"[IMAGE] file_path={file_path}")
            print(f"[IMAGE] exists={file_path.exists()}")

            if not file_path.exists():
                print("[IMAGE] JSON FILE NOT FOUND")
                return []

            with open(
                file_path,
                "r",
                encoding="utf-8"
            ) as f:

                images = json.load(f)

            print(f"[IMAGE] loaded {len(images)} images")

            result = []
            seen = set()
            # for image in images:

            #     result.append(
            #         {
            #             "id": image.get("Id"),
            #             "title": image.get("Title"),
            #             "about": image.get("About"),
            #             "format": image.get("format"),
            #             "base64": image.get("base64")
            #         }
            #     )
            for image in images:

                image_id = str(image.get("Id") or "").strip()
                base64 = str(image.get("base64") or "").strip()

                # Use image ID if available, otherwise base64 as unique key
                unique_key = image_id if image_id else base64

                if unique_key in seen:
                    continue

                seen.add(unique_key)

                result.append(
                    {
                        "id": image.get("Id"),
                        "title": image.get("Title"),
                        "about": image.get("About"),
                        "format": image.get("format"),
                        "base64": image.get("base64")
                    }
                )

            print(f"[IMAGE] returning {len(result)} images")

            return result

        except Exception as e:
            print(f"[IMAGE] ERROR: {e}")
            return []