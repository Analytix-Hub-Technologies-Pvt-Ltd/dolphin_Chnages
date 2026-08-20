import json
import asyncio
from datetime import datetime, date
from typing import List, Dict, Any
from models.database import get_pool
from course_sync.external_api_client import ExternalAPIClient
from course_sync.course_content_processor import CourseContentProcessor
from course_sync.course_sync_models import CourseListItem
from loguru import logger
import pandas as pd
import io, os
import requests
import uuid 
import httpx
from pypdf import PdfReader
from urllib.parse import urlparse

class CourseSyncService:
    def __init__(self, api_client: ExternalAPIClient):
        self.api_client = api_client
        self.content_processor = CourseContentProcessor()
    
    async def sync_master_course_data(self, courses: List[CourseListItem]):
        pool = await get_pool()
        inserted_count = 0
        updated_count = 0
        
        async with pool.acquire() as conn:
            async with conn.transaction():
                for course in courses:
                    existing = await conn.fetchrow(
                        "SELECT course_name FROM master_course_data WHERE course_code = $1",
                        course.CourseCode
                    )
                    
                    if existing:
                        if existing['course_name'] != course.Name:
                            await conn.execute(
                                "UPDATE master_course_data SET course_name = $1 WHERE course_code = $2",
                                course.Name, course.CourseCode
                            )
                            updated_count += 1
                    else:
                        await conn.execute(
                            "INSERT INTO master_course_data (course_code, course_name, course_added) VALUES ($1, $2, $3)",
                            course.CourseCode, course.Name, date.today()
                        )
                        inserted_count += 1
                
                return {"inserted": inserted_count, "updated": updated_count, "deleted": 0}
    
    async def sync_course_content(self, courses: List[CourseListItem]):
        content_processed = 0
        content_errors = 0
        error_details = []
        failed_courses = []

        logger.info(f"Processing content for {len(courses)} courses sequentially")

        for course in courses:
            success = False

            for attempt in range(1, 4):
                try:
                    if attempt > 1:
                        logger.info(f"Retry attempt {attempt}/3 for course: {course.CourseCode}")
                        await asyncio.sleep(2)

                    pool = await get_pool()
                    if pool._closed:
                        raise RuntimeError("Database pool is closed")

                    topics_count = await self._process_course_content(course, pool)
                    content_processed += topics_count
                    success = True
                    break

                except Exception as e:
                    error_msg = str(e)

                    if "pool is closed" in error_msg.lower():
                        logger.error("Database pool is closed. Aborting sync.")
                        raise

                    if attempt < 3:
                        logger.warning(f"Attempt {attempt} failed for {course.CourseCode}: {e}")
                    else:
                        logger.error(f"All 3 attempts failed for course {course.CourseCode}: {e}")
                        if error_msg not in error_details:
                            error_details.append(error_msg)
                        content_errors += 1

            if not success:
                failed_courses.append(course.CourseCode)

        logger.info(
            f"Content sync: {content_processed} topics processed, "
            f"{content_errors} errors, failed courses: {failed_courses}"
        )

        return {
            "topics_processed": content_processed,
            "errors": content_errors,
            "error_details": error_details,
            "failed_courses": failed_courses
        }

    async def _process_course_content(self, course, pool):
        logger.info(f"Processing course: {course.CourseCode}")
        
        try:
            content_response = await self.api_client.get_course_content(course.CourseCode)
        except Exception as e:
            raise Exception(f"External API connection failed - unable to fetch course content: {str(e)}")
        
        try:
            zip_content = await self.api_client.download_content_zip(content_response.value)
        except Exception as e:
            raise Exception(f"ZIP download failed - network or server issue: {str(e)}")
        
        try:
            course_records = await self.content_processor.process_course_zip(zip_content, course.CourseCode)
        except Exception as e:
            raise Exception(f"Content processing failed - invalid ZIP or missing files: {str(e)}")
        
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute("DELETE FROM course_content WHERE course_code = $1", course.CourseCode)
                    
                    for record in course_records:
                        content = record["topic_content"] or ''
                        sanitized_content = content.replace('\x00', '').encode('utf-8', 'ignore').decode('utf-8')
                        
                        await conn.execute(
                            """INSERT INTO course_content 
                               (course_code, topic_code, topic_name, topic_video, 
                                topic_image, topic_pdf, topic_content, fetched_on)
                               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                            record["course_code"], record["topic_code"], record["topic_name"],
                            json.dumps(record["topic_video"] or []),
                            json.dumps(record["topic_image"] or []),
                            json.dumps(record["topic_pdf"] or []),
                            sanitized_content, record["fetched_on"]
                        )
                    
                    logger.info(f"Stored {len(course_records)} topics for {course.CourseCode}")
                    return len(course_records)
        except Exception as e:
            raise Exception(f"Database operation failed - connection or query error: {str(e)}")
    
    async def retry_failed_courses(self, course_codes: List[str]) -> Dict[str, Any]:
        results = {
            "total_courses": len(course_codes),
            "successful": [],
            "failed": [],
            "retry_attempts": {}
        }
        
        pool = await get_pool()
        
        for course_code in course_codes:
            logger.info(f"Starting retry process for course: {course_code}")
            success = False
            
            for attempt in range(1, 4):
                try:
                    logger.info(f"Attempt {attempt}/3 for course: {course_code}")
                    
                    course_item = CourseListItem(CourseCode=course_code, Name=course_code)
                    
                    await self.sync_master_course_data([course_item])
                    topics_count = await self._process_course_content(course_item, pool)
                    
                    logger.info(f"Successfully processed {course_code} with {topics_count} topics on attempt {attempt}")
                    results["successful"].append(course_code)
                    results["retry_attempts"][course_code] = attempt
                    success = True
                    break
                    
                except Exception as e:
                    logger.warning(f"Attempt {attempt} failed for {course_code}: {str(e)}")
                    if "Internal Server Error" in str(e) or "server error (500)" in str(e).lower():
                        logger.warning(f"Course {course_code} appears to have server-side issues - may be corrupted or temporarily unavailable")
                    if attempt < 3:
                        await asyncio.sleep(2)
                    continue
            
            if not success:
                logger.error(f"All 3 attempts failed for course: {course_code}")
                results["failed"].append(course_code)
                results["retry_attempts"][course_code] = 3
        
        logger.info(f"Retry completed: {len(results['successful'])} successful, {len(results['failed'])} failed")
        return results
    
    async def run_full_sync(self, updated_after: str = None, changed: int = None) -> Dict[str, Any]:
        try:
            logger.info(f"Starting sync with UpdatedAfter: {updated_after}, Changed: {changed}")
            
            if updated_after:
                course_list_response = await self.api_client.get_course_list(updated_after)
            else:
                course_list_response = await self.api_client.get_all_courses()
            
            if not course_list_response.courses:
                logger.info("No courses to sync")
                return {"status": "success", "courses_processed": 0}
            
            all_courses = course_list_response.courses
            
            if changed is not None:
                courses_to_process = [course for course in all_courses if course.Changed == changed]
                logger.info(f"Total courses from API: {len(all_courses)}")
                logger.info(f"Filtered courses (Changed={changed}): {len(courses_to_process)}")
            else:
                courses_to_process = all_courses
                logger.info(f"Processing all {len(courses_to_process)} courses (no Changed filter)")
            
            if not courses_to_process:
                logger.info("No courses match the filter criteria")
                return {"status": "success", "courses_processed": 0}
            
            phase_b_stats = await self.sync_master_course_data(courses_to_process)
            phase_c_stats = await self.sync_course_content(courses_to_process)
            
            logger.info(f"Sync completed: {len(courses_to_process)} courses processed")
            return {
                "status": "success", 
                "courses_processed": len(courses_to_process),
                "total_from_api": len(all_courses),
                "phase_b_details": phase_b_stats,
                "phase_c_details": phase_c_stats
            }
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            return {"status": "error", "message": str(e)}
    
    
    async def run_full_sync_master(self, updated_after: str, changed: int = None) -> Dict[str, Any]:
        try:
            logger.info(f"Starting sync with UpdatedAfter: {updated_after}, Changed: {changed}")
            course_list_response = await self.api_client.get_course_list(updated_after)
            
            if not course_list_response.courses:
                logger.info("No courses to sync")
                return {"status": "success", "courses_processed": 0}
            
            all_courses = course_list_response.courses
            
            if changed is not None:
                courses_to_process = [course for course in all_courses if course.Changed == changed]
                logger.info(f"Total courses from API: {len(all_courses)}")
                logger.info(f"Filtered courses (Changed={changed}): {len(courses_to_process)}")
            else:
                courses_to_process = all_courses
                logger.info(f"Processing all {len(courses_to_process)} courses (no Changed filter)")
            
            if not courses_to_process:
                logger.info("No courses match the filter criteria")
                return {"status": "success", "courses_processed": 0}
            
            phase_b_stats = await self.sync_master_course_data(courses_to_process)
           
            logger.info(f"Sync completed: {len(courses_to_process)} courses processed")
            return {
                "status": "success", 
                "courses_processed": len(courses_to_process),
                "total_from_api": len(all_courses),
                "phase_b_details": phase_b_stats
            }
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            return {"status": "error", "message": str(e)}
    
    async def run_full_sync_content(self, Offset: int = None, Limit: int = None) -> Dict[str, Any]:
        try:
            logger.info(f"Starting sync with Offset: {Offset}, Limit: {Limit}")

            course_list_response = await self.get_course_list_master(
                limit=Limit,
                offset=Offset
            )

            if not course_list_response:
                logger.info("No courses to sync")
                return {"status": "success", "courses_processed": 0}

            courses_to_process = [
                CourseListItem(
                    CourseId=row["CourseId"],
                    CourseCode=row["CourseCode"],
                    Name=row["Name"],
                    FetchedOn="2025-12-22",
                    Changed=1
                )
                for row in course_list_response
            ]


            phase_c_stats = await self.sync_course_content(courses_to_process)

            logger.info(f"Sync completed: {len(courses_to_process)} courses processed")
            return {
                "status": "success",
                "courses_processed": len(courses_to_process),
                "total_from_db": len(courses_to_process),
                "phase_c_details": phase_c_stats
            }

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            return {"status": "error", "message": str(e)}

    async def get_course_list_master(self, limit: int, offset: int):
        query = """
        SELECT
            course_id   AS "CourseId",
            course_code AS "CourseCode",
            course_name AS "Name"
        FROM master_course_data
        ORDER BY course_id
        LIMIT $1 OFFSET $2
        """

        pool = await get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, limit, offset)

        return [dict(row) for row in rows]

    async def run_delete_sync(self, updated_after: str = None) -> Dict[str, Any]:
        try:
            if updated_after:
                courses_response = await self.api_client.get_course_list(updated_after)
            else:
                courses_response = await self.api_client.get_all_courses()
            
            if not courses_response.courses:
                return {"status": "success", "deleted": 0}
            
            api_course_codes = set(course.CourseCode for course in courses_response.courses)
            
            pool = await get_pool()
            async with pool.acquire() as conn:
                if updated_after:
                    existing_rows = await conn.fetch(
                        "SELECT course_code FROM master_course_data WHERE course_added >= $1",
                        datetime.strptime(updated_after, "%Y-%m-%d").date()
                    )
                else:
                    existing_rows = await conn.fetch("SELECT course_code FROM master_course_data")
                
                db_course_codes = set(row['course_code'] for row in existing_rows)
                courses_to_delete = db_course_codes - api_course_codes
                deleted_count = 0
                
                if courses_to_delete:
                    async with conn.transaction():
                        for course_code in courses_to_delete:
                            await conn.execute("DELETE FROM course_content WHERE course_code = $1", course_code)
                            await conn.execute("DELETE FROM master_course_data WHERE course_code = $1", course_code)
                            deleted_count += 1
                
                return {
                    "status": "success",
                    "deleted": deleted_count,
                    "api_courses": len(api_course_codes),
                    "db_courses_before": len(db_course_codes),
                    "filter_date": updated_after
                }
                
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def sync_course_content_from_excel(self, file_bytes: bytes, start_row: int, end_row: int, pool):

        logger.info("Processing Excel content upload")

        encrypted_files = []
        unprocessed_files = []
        download_failures = []
        db_failures = []

        df = pd.read_excel(
            io.BytesIO(file_bytes),
            engine="openpyxl",
            header=1
        )

        DATA_START_ROW = 3

        start_index = start_row - DATA_START_ROW
        end_index = end_row - DATA_START_ROW

        if start_index < 0:
            start_index = 0

        df = df.iloc[start_index : end_index + 1]

        logger.info(f"Excel rows selected: {start_row} to {end_row}")
        logger.info(f"Total rows after slicing: {len(df)}")

        course_records = []
        extracted_course_codes = set()

        async with httpx.AsyncClient(timeout=30) as client:

            for index, row in df.iterrows():
                try:
                    # Column A → Topic Name
                    topic_name = str(row.iloc[0]).strip()

                    # Column E → PDF URL
                    pdf_link = str(row.iloc[4]).strip()

                    if not topic_name or not pdf_link or pdf_link.lower() == "nan":
                        continue

                    # Extract course_code from URL
                    parsed_url = urlparse(pdf_link)
                    file_name = os.path.basename(parsed_url.path)
                    extracted_course_code = os.path.splitext(file_name)[0]

                    extracted_course_codes.add(extracted_course_code)

                    # Download PDF
                    response = await client.get(pdf_link)

                    if response.status_code != 200:
                        raise Exception(f"Failed to download PDF: {pdf_link}")

                    pdf_bytes = response.content

                    extracted_text = ""
                    try:
                        reader = PdfReader(io.BytesIO(pdf_bytes))

                        # 🔐 Encrypted file
                        if reader.is_encrypted:

                            encrypted_files.append({
                                "row_index": index + DATA_START_ROW,
                                "course_code": extracted_course_code,
                                "file_url": pdf_link
                            })

                            logger.warning(f"Encrypted PDF skipped: {pdf_link}")
                            continue

                        for page in reader.pages:
                            text = page.extract_text()
                            if text:
                                extracted_text += text + "\n"

                        if not extracted_text.strip():
                            unprocessed_files.append({
                                "row_index": index + DATA_START_ROW,
                                "course_code": extracted_course_code,
                                "file_url": pdf_link,
                                "reason": "No readable text (Image-based or empty PDF)"
                            })

                            logger.warning(f"No readable text found in PDF: {pdf_link}")
                            continue

                    except PdfReadError as pdf_error:

                        unprocessed_files.append({
                            "row_index": index + DATA_START_ROW,
                            "course_code": extracted_course_code,
                            "file_url": pdf_link
                        })

                        logger.error(f"PDF read error: {pdf_error}")
                        continue

                    record = {
                        "course_code": extracted_course_code,
                        "topic_code": "PDF",
                        "topic_name": topic_name,
                        "topic_video": [],
                        "topic_image": [],
                        "topic_pdf": [],
                        "topic_content": extracted_text,
                        "fetched_on": date.today()
                    }

                    course_records.append(record)

                except Exception as row_error:
                    logger.error(f"Row {index + 1} failed during processing: {row_error}")
                    download_failures.append({
                        "row_index": index + DATA_START_ROW,
                        "course_code": extracted_course_code,
                        "file_url": pdf_link
                    })
                    download_failures += 1
                    continue

        if not course_records:
            logger.warning("No valid rows found in Excel")
            return {
                "inserted": 0,
                "failed": download_failures,
                "db_failed": 0,
                "details": failed_rows
            }

        # ===============================
        # DATABASE INSERT
        # ===============================

        async with pool.acquire() as conn:
            async with conn.transaction():

                for record in course_records:
                    try:
                        sanitized_content = (
                            (record["topic_content"] or "")
                            .replace('\x00', '')
                            .encode('utf-8', 'ignore')
                            .decode('utf-8')
                        )

                        # Check if course already exists
                        existing = await conn.fetchrow(
                            "SELECT topic_content FROM course_content WHERE course_code = $1",
                            record["course_code"]
                        )

                        if existing:
                            # Update existing content
                            await conn.execute(
                                """
                                UPDATE course_content
                                SET topic_content = $1,
                                    fetched_on = $2
                                WHERE course_code = $3
                                """,
                                sanitized_content,
                                record["fetched_on"],
                                record["course_code"]
                            )

                        else:
                            # Insert new row
                            await conn.execute(
                                """
                                INSERT INTO course_content 
                                (course_code, topic_code, topic_name, topic_video, 
                                topic_image, topic_pdf, topic_content, fetched_on)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                                """,
                                record["course_code"],
                                record["topic_code"],
                                record["topic_name"],
                                json.dumps(record["topic_video"]),
                                json.dumps(record["topic_image"]),
                                json.dumps(record["topic_pdf"]),
                                sanitized_content,
                                record["fetched_on"]
                            )

                    except Exception as db_error:
                        logger.error(f"DB insert failed for course {record['course_code']}: {db_error}")
                        db_failures.append({
                            "course_code": record["course_code"],
                            "error": str(db_error)
                        })

        inserted_count = len(course_records) - len(db_failures)

        logger.info(f"Inserted: {inserted_count}")
        logger.info(f"Download Failures: {download_failures}")
        logger.info(f"DB Failures: {db_failures}")
        logger.info(f"Unprocessed Files: {unprocessed_files}")
        logger.info(f"Encrypted Files: {encrypted_files}")

        return {
            "inserted": inserted_count,
            "unprocessed_files": unprocessed_files,
            "Failed_Files": encrypted_files+download_failures+db_failures
        }