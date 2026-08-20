import json
import zipfile
import tempfile
import os
import aiohttp
import base64
import io
from typing import Dict, List, Optional, Any
from datetime import datetime
from bs4 import BeautifulSoup
from loguru import logger
import PyPDF2
from PIL import Image
from config import settings

class CourseContentProcessor:
    
    def __init__(self):
        self.api_key = "CDDDCD43BC944F2AA5DC501FB2CDE136"
        self.base_url = "https://ai.marinerskills.com/aidata"


    def _compress_and_resize_image(self,image_data: bytes,image_id: str,max_width: int = 400,quality: int = 40) -> bytes:
        """
        Resize and compress image aggressively to reduce size.
        """
        try:
            img = Image.open(io.BytesIO(image_data))

            # Convert to RGB (required for JPEG)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # Resize while keeping aspect ratio
            if img.width > max_width:
                ratio = max_width / float(img.width)
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.LANCZOS)

            output = io.BytesIO()
            img.save(
                output,
                format="JPEG",      # Force JPEG for max compression
                quality=quality,    # Lower = more compression (20–40 good)
                optimize=True
            )

            compressed_data = output.getvalue()

            logger.info(
                f"Compressed {image_id}: "
                f"{len(image_data)} → {len(compressed_data)} bytes"
            )

            return compressed_data

        except Exception as e:
            logger.warning(f"Compression failed for {image_id}: {e}")
            return image_data  # fallback to original
    
    def _validate_image_data(self, image_data: bytes, image_id: str, min_width: int = 10, min_height: int = 10, 
                            min_size: int = 100, max_size: int = 10 * 1024 * 1024) -> bool:
        """Validate image data to ensure it's a valid image file.
        
        Args:
            image_data: Raw image bytes
            image_id: Image identifier for logging
            min_width: Minimum image width in pixels (default: 10)
            min_height: Minimum image height in pixels (default: 10)
            min_size: Minimum file size in bytes (default: 100)
            max_size: Maximum file size in bytes (default: 10MB)
            
        Returns:
            True if image is valid, False otherwise
        """
        try:
            # Check file size
            if len(image_data) < min_size:
                logger.warning(f"Image {image_id} too small: {len(image_data)} bytes (min: {min_size})")
                return False
            
            if len(image_data) > max_size:
                logger.warning(f"Image {image_id} too large: {len(image_data)} bytes (max: {max_size})")
                return False
            
            # Verify it's a valid image
            img = Image.open(io.BytesIO(image_data))
            img.verify()
            
            # Re-open for dimension checks (verify() closes the file)
            img = Image.open(io.BytesIO(image_data))
            
            # Check minimum dimensions
            if img.width < min_width or img.height < min_height:
                logger.warning(f"Image {image_id} dimensions too small: {img.width}x{img.height} (min: {min_width}x{min_height})")
                return False
            
            logger.debug(f"Image {image_id} validated: {img.width}x{img.height}, {len(image_data)} bytes, format: {img.format}")
            return True
            
        except Exception as e:
            logger.warning(f"Invalid image data for {image_id}: {e}")
            return False
    
    async def process_course_zip(self, zip_content: bytes, course_code: str) -> List[Dict[str, Any]]:
        course_records = []
        
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, f"{course_code}.zip")
            with open(zip_path, 'wb') as f:
                f.write(zip_content)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            topics_data = self._read_json_file(temp_dir, "topic.json")
            if not topics_data:
                return []
            
            videos_data = self._read_json_file(temp_dir, "video.json") or []
            images_data = self._read_json_file(temp_dir, "image.json") or []
            pdfs_data = self._read_json_file(temp_dir, "pdf.json") or []
            fetch_data = self._read_json_file(temp_dir, "fetch.json")
            
            self._pdf_text_content = {}
            self._pdf_images = {}
            
            video_mapping = await self._create_topic_mapping(videos_data, "Videos")
            image_mapping = await self._create_topic_mapping(images_data, "Images")
            pdf_mapping = await self._create_topic_mapping(pdfs_data, "Pdfs")
            
            fetched_on = datetime.now().date()
            if fetch_data and "FetchDate" in fetch_data:
                try:
                    fetched_on = datetime.strptime(fetch_data["FetchDate"], "%Y-%m-%d").date()
                except ValueError:
                    pass
            
            topics_list = topics_data if isinstance(topics_data, list) else [topics_data]
            
            total_images_filtered = 0
            total_videos_filtered = 0
            total_pdfs_filtered = 0
            
            for topic in topics_list:
                topic_code = topic.get("TopicCode")
                topic_name = topic.get("Name")
                
                if not topic_code or not topic_name:
                    continue
                
                all_images = image_mapping.get(topic_code, [])
                pdf_images = getattr(self, '_pdf_images', {}).get(topic_code, [])
                all_images.extend(pdf_images)
                
                # Filter out images with empty URLs (invalid images)
                valid_images = [img for img in all_images if img.get("Url", "").strip()]
                images_filtered = len(all_images) - len(valid_images)
                total_images_filtered += images_filtered
                
                # Filter out videos with empty URLs
                all_videos = video_mapping.get(topic_code, [])
                valid_videos = [vid for vid in all_videos if vid.get("Url", "").strip()]
                videos_filtered = len(all_videos) - len(valid_videos)
                total_videos_filtered += videos_filtered
                
                # Filter out PDFs with empty Links
                all_pdfs = pdf_mapping.get(topic_code, [])
                valid_pdfs = [pdf for pdf in all_pdfs if pdf.get("Link", "").strip()]
                pdfs_filtered = len(all_pdfs) - len(valid_pdfs)
                total_pdfs_filtered += pdfs_filtered
                
                if images_filtered > 0 or videos_filtered > 0 or pdfs_filtered > 0:
                    logger.info(f"Topic {topic_code}: Filtered {images_filtered} invalid images, "
                               f"{videos_filtered} invalid videos, {pdfs_filtered} invalid PDFs")
                
                record = {
                    "course_code": course_code,
                    "topic_code": topic_code,
                    "topic_name": topic_name,
                    "topic_video": valid_videos,
                    "topic_image": valid_images,
                    "topic_pdf": valid_pdfs,
                    "topic_content": self._merge_content(temp_dir, topic_code),
                    "fetched_on": fetched_on
                }
                
                course_records.append(record)
            
            if total_images_filtered > 0 or total_videos_filtered > 0 or total_pdfs_filtered > 0:
                logger.info(f"Course {course_code} total filtered: {total_images_filtered} images, "
                           f"{total_videos_filtered} videos, {total_pdfs_filtered} PDFs")


        
        return course_records
    
    def _read_json_file(self, temp_dir: str, filename: str) -> Optional[Any]:
        file_path = os.path.join(temp_dir, filename)
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return None
    
    async def _create_topic_mapping(self, data: Any, content_key: str) -> Dict[str, Any]:
        mapping = {}
        if not data:
            return mapping
        
        data_list = data if isinstance(data, list) else [data]
        
        for item in data_list:
            topic_code = item.get("TopicCode")
            if topic_code: 
                content = item.get(content_key, [])
                
                if content_key == "Videos" and content:
                    enhanced_videos = []
                    for video in content:
                        video_id = video.get("Id")
                        if video_id:
                            try:
                                video_data = await self._get_video_url(video_id, video)
                                enhanced_videos.append(video_data)
                            except Exception as e:
                                logger.warning(f"Failed to get video URL for {video_id}: {e}")
                                enhanced_videos.append({
                                    "Id": video_id,
                                    "About": video.get("About", ""),
                                    "Title": video.get("Title", ""),
                                    "Captions": video.get("Captions", []),
                                    "Duration": video.get("Duration", ""),
                                    "Thumbnail": f"https://ai.marinerskills.com/mp4/{video_id}/thumbnail.jpg",
                                    "Url": ""
                                })
                    mapping[topic_code] = enhanced_videos
                
                elif content_key == "Images" and content:
                    enhanced_images = []
                    for image in content:
                        image_id = image.get("Id")
                        if image_id:
                            try:
                                image_data = await self._get_image_data(image_id, image)
                                enhanced_images.append(image_data)
                            except Exception as e:
                                logger.warning(f"Failed to get image data for {image_id}: {e}")
                                enhanced_images.append({
                                    "Id": image_id,
                                    "About": image.get("About", ""),
                                    "Title": image.get("Title", ""),
                                    "Url": ""
                                })
                    mapping[topic_code] = enhanced_images
                
                elif content_key == "Pdfs" and content:
                    enhanced_pdfs = []
                    for pdf in content:
                        pdf_id = pdf.get("Id")
                        pdf_link = pdf.get("Link")
                        
                        if not pdf_id and pdf_link:
                            full_link = f"https://ai.marinerskills.com/{pdf_link}" if not pdf_link.startswith("http") else pdf_link
                            
                            pdf_data = {
                                "Link": full_link,
                                "Title": pdf.get("Title", ""),
                                "About": pdf.get("About", "")
                            }
                            enhanced_pdfs.append(pdf_data)
                            
                            temp_id = pdf_link.split("/")[-1].replace(".pdf", "")
                            images, text = await self._extract_pdf_content(full_link, temp_id, topic_code, pdf_data)
                            
                            if images:
                                if not hasattr(self, '_pdf_images'):
                                    self._pdf_images = {}
                                if topic_code not in self._pdf_images:
                                    self._pdf_images[topic_code] = []
                                self._pdf_images[topic_code].extend(images)
                            
                            if text:
                                if not hasattr(self, '_pdf_text_content'):
                                    self._pdf_text_content = {}
                                if topic_code not in self._pdf_text_content:
                                    self._pdf_text_content[topic_code] = ""
                                self._pdf_text_content[topic_code] += f" {text}"
                            
                            continue
                        
                        if pdf_id:
                            try:
                                pdf_data = await self._get_pdf_data(pdf_id, pdf)
                                enhanced_pdfs.append(pdf_data)
                                
                                if pdf_data.get("Link"):
                                    images, text = await self._extract_pdf_content(pdf_data["Link"], pdf_id, topic_code, pdf_data)
                                    
                                    if images:
                                        if not hasattr(self, '_pdf_images'):
                                            self._pdf_images = {}
                                        if topic_code not in self._pdf_images:
                                            self._pdf_images[topic_code] = []
                                        self._pdf_images[topic_code].extend(images)
                                    
                                    if text:
                                        if not hasattr(self, '_pdf_text_content'):
                                            self._pdf_text_content = {}
                                        if topic_code not in self._pdf_text_content:
                                            self._pdf_text_content[topic_code] = ""
                                        self._pdf_text_content[topic_code] += f" {text}"
                                        
                            except Exception as e:
                                logger.warning(f"Failed to get PDF data for {pdf_id}: {e}")
                                enhanced_pdfs.append({
                                    "Link": f"https://ai.marinerskills.com/{pdf['Link']}" if pdf.get("Link") and pdf["Link"].strip() else "",
                                    "About": pdf.get("About", ""),
                                    "Title": pdf.get("Title", "")
                                })
                        else:
                            enhanced_pdfs.append({
                                "Link": f"https://ai.marinerskills.com/{pdf['Link']}" if pdf.get("Link") and pdf["Link"].strip() else "",
                                "About": pdf.get("About", ""),
                                "Title": pdf.get("Title", "")
                            })
                    mapping[topic_code] = enhanced_pdfs
                
                else:
                    mapping[topic_code] = content if content else []
        
        return mapping
    
    def _merge_content(self, temp_dir: str, topic_code: str) -> str:
        html_content = self._read_html_content(temp_dir, topic_code)
        pdf_content = getattr(self, '_pdf_text_content', {}).get(topic_code, "")
        
        combined_content = html_content
        if pdf_content:
            if html_content:
                combined_content += "\n\n" + pdf_content
            else:
                combined_content = pdf_content
        
        return combined_content.strip()
    
    async def _extract_pdf_content(self, pdf_url: str, pdf_id: str, topic_code: str, pdf_metadata: Dict = None) -> tuple[List[Dict], str]:
        images = []
        text_content = ""
        
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(pdf_url) as response:
                    if response.status != 200:
                        return images, text_content
                    
                    pdf_data = await response.read()
            
            os.makedirs("./storage/pdf_images", exist_ok=True)
            
            try:
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_data))
                
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    
                    try:
                        page_text = page.extract_text()
                        if page_text and page_text.strip():
                            lines = page_text.split('\n')
                            page_lines = []
                            
                            for line in lines:
                                cleaned_line = line.strip()
                                if cleaned_line:  
                                    page_lines.append(cleaned_line)
                            
                            if page_lines:
                                page_content = '\n'.join(page_lines)
                                if text_content:
                                    text_content += '\n\n' + page_content
                                else:
                                    text_content = page_content
                    except Exception:
                        pass
                    
                    if '/XObject' in page['/Resources']:
                        xObject = page['/Resources']['/XObject'].get_object()
                        
                        for obj in xObject:
                            if xObject[obj]['/Subtype'] == '/Image':
                                try:
                                    img_obj = xObject[obj]
                                    img_data = img_obj.get_data()

                                    # Compress PDF image
                                    img_data = self._compress_and_resize_image(img_data, img_id)
                                    
                                    # Validate image data before saving
                                    img_id = f"{pdf_id}_img_{page_num}_{obj[1:]}"
                                    if not self._validate_image_data(img_data, img_id):
                                        logger.warning(f"Skipping invalid PDF image: {img_id}")
                                        continue
                                    
                                    img_ext = 'png'
                                    img_filename = f"{img_id}.{img_ext}"
                                    img_path = f"./storage/pdf_images/{img_filename}"
                                    
                                    with open(img_path, 'wb') as img_file:
                                        img_file.write(img_data)
                                    
                                    images.append({
                                        "Id": "",
                                        "Title": pdf_metadata.get("Title", "") if pdf_metadata else "",
                                        "About": pdf_metadata.get("About", "") if pdf_metadata else "",
                                        "Url": f"{settings.image_base_url}/storage/pdf_images/{img_filename}"
                                    })
                                    
                                except Exception as e:
                                    logger.warning(f"Failed to extract PDF image {obj}: {e}")
                                    continue
                                    
            except Exception:
                pass
            
        except Exception:
            pass
        
        return images, text_content.strip()
    
    def _read_html_content(self, temp_dir: str, topic_code: str) -> str:
        html_file = os.path.join(temp_dir, f"{topic_code}.htm")
        if os.path.exists(html_file):
            try:
                with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                    html_content = f.read()
                
                soup = BeautifulSoup(html_content, 'html.parser')
                for script in soup(["script", "style"]):
                    script.decompose()
                
                text_content = soup.get_text(separator=' ', strip=True)
                return ' '.join(text_content.split())
                
            except Exception:
                pass
        
        return ""
    
    async def _get_video_url(self, video_id: str, original_video: Dict[str, Any] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/VideoUrl"
        payload = {"Key": self.api_key, "ID": video_id}
        
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    raise Exception(f"API request failed: {response.status}")
                
                data = await response.json()
                if data.get("errorCode", 0) != 0:
                    raise Exception(f"API error: {data.get('error', 'Unknown error')}")
                
                return {
                    "Id": video_id,
                    "About": original_video.get("About", "") if original_video else "",
                    "Title": original_video.get("Title", "") if original_video else "",
                    "Captions": original_video.get("Captions", []) if original_video else [],
                    "Duration": original_video.get("Duration", "") if original_video else "",
                    "Thumbnail": f"https://ai.marinerskills.com/mp4/{video_id}/thumbnail.jpg",
                    "Url": data["value"]
                }
    
    async def _get_image_data(self, image_id: str, original_image: Dict[str, Any] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/ImageData"
        payload = {"Key": self.api_key, "ID": image_id}
        
        connector = aiohttp.TCPConnector(ssl=False)  
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    raise Exception(f"API request failed: {response.status}")
                
                data = await response.json()
                if data.get("errorCode", 0) != 0:
                    raise Exception(f"API error: {data.get('error', 'Unknown error')}")
                
                image_url = data["value"]
                if image_url.startswith("data:image/"):
                    try:
                        os.makedirs("./storage/images", exist_ok=True)
                        
                        header, encoded = image_url.split(',', 1)
                        format_info = header.split(';')[0].split('/')[1]
                        image_data = base64.b64decode(encoded)

                        # Compress image before validation
                        image_data = self._compress_and_resize_image(image_data, image_id)
                        
                        # Validate image data before saving
                        if not self._validate_image_data(image_data, image_id):
                            logger.warning(f"Skipping invalid image: {image_id}")
                            return {
                                "Id": image_id,
                                "About": original_image.get("About", "") if original_image else "",
                                "Title": original_image.get("Title", "") if original_image else "",
                                "Url": ""
                            }
                        
                        filename = f"{image_id}.{format_info}"
                        file_path = f"./storage/images/{filename}"
                        
                        with open(file_path, 'wb') as f:
                            f.write(image_data)
                        
                        image_url = f"{settings.image_base_url}/storage/images/{filename}"
                    except Exception as e:
                        logger.error(f"Failed to process image {image_id}: {e}")
                        image_url = ""
                
                return {
                    "Id": image_id,
                    "About": original_image.get("About", "") if original_image else "",
                    "Title": original_image.get("Title", "") if original_image else "",
                    "Url": image_url
                }
    
    async def _get_pdf_data(self, pdf_id: str, original_pdf: Dict[str, Any] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/PdfData"
        payload = {"Key": self.api_key, "ID": pdf_id}
        
        connector = aiohttp.TCPConnector(ssl=False)  
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    raise Exception(f"API request failed: {response.status}")
                
                data = await response.json()
                if data.get("errorCode", 0) != 0:
                    raise Exception(f"API error: {data.get('error', 'Unknown error')}")
                
                api_data = data.get("value", {})
                
                return {
                    "Link": f"https://ai.marinerskills.com/{original_pdf['Link']}" if original_pdf and original_pdf.get("Link") and original_pdf["Link"].strip() else "",
                    "About": api_data.get("About", original_pdf.get("About", "") if original_pdf else ""),
                    "Title": api_data.get("Title", original_pdf.get("Title", "") if original_pdf else "")
                }