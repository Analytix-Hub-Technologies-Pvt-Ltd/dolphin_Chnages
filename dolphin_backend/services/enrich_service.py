# services/enrich_service.py

class EnrichService:
    def __init__(self, chat_service):
        self.chat_service = chat_service

    async def enrich(self, chunks):
        videos = self.chat_service._build_video_suggestions(chunks)

        images = []
        pdfs = []

        for c in chunks:
            images.extend(c.get("images", []))
            pdfs.extend(c.get("pdfs", []))

        return {
            "videos": videos[:10],
            "images": images[:5],
            "pdfs": pdfs[:5]
        }