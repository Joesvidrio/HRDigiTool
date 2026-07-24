import fitz
import os
import tempfile
import shutil
import math
from utils import get_resource_path

class PDFProcessor:
    """
    Core backend processor for PDF manipulation using PyMuPDF (fitz).
    
    This class provides static methods to handle heavy PDF operations without 
    blocking the UI thread (when used with background workers). It includes 
    features for rendering thumbnails, detecting blank pages, merging, splitting, 
    watermarking, and managing document security.
    """

    @staticmethod
    def get_pdf_thumbnails(pdf_path):
        """
        Generates low-resolution PNG thumbnails for all pages in a PDF.
        
        Args:
            pdf_path (str): Absolute path to the source PDF file.
            
        Returns:
            list[bytes]: A list of byte arrays representing PNG images. 
                         Returns an empty list if the operation fails.
        """
        try:
            doc = fitz.open(pdf_path)
            thumbnails = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                # Scale down matrix (20% of original size) for faster rendering 
                # and to keep memory footprint minimal during UI loads.
                pix = page.get_pixmap(matrix=fitz.Matrix(0.2, 0.2)) 
                thumbnails.append(pix.tobytes("png"))
                
            doc.close()
            return thumbnails
            
        except Exception as e:
            print(f"Error generating thumbnails: {e}")
            return []

    @staticmethod
    def get_blank_pages(pdf_path, tolerance=5):
        """
        Detects blank pages by analyzing pixel standard deviation.
        Uses a highly downscaled render to ignore standard scanner artifacts (dust/shadows).
        
        Args:
            pdf_path (str): Path to the PDF file.
            tolerance (int): Standard deviation threshold. Lower is stricter. Default is 5.
            
        Returns:
            list[int]: A list of 1-based page numbers identified as visually blank.
        """
        blank_pages = []
        try:
            doc = fitz.open(pdf_path)
            
            for i in range(len(doc)):
                page = doc[i]
                
                # Render at 5% scale to average out microscopic noise/dust
                pix = page.get_pixmap(matrix=fitz.Matrix(0.05, 0.05))
                samples = pix.samples
                text = page.get_text().strip()
                
                # If page is completely empty (no pixels to analyze)
                if not samples:
                    if not text:
                        blank_pages.append(i + 1)
                    continue
                    
                # Calculate pixel variance and standard deviation
                mean = sum(samples) / len(samples)
                variance = sum((x - mean) ** 2 for x in samples) / len(samples)
                std_dev = math.sqrt(variance)
                
                # If the image is highly uniform (low std_dev) AND contains no text layer
                if std_dev < tolerance and not text:
                    blank_pages.append(i + 1)
                    
            doc.close()
            
        except Exception as e:
            print(f"Error detecting blank pages: {e}")
            
        return blank_pages

    @staticmethod
    def merge_files_to_temp(file_paths, output_path, page_size="Original"):
        """
        Merges multiple PDFs and/or images into a single temporary PDF file.
        
        Args:
            file_paths (list[str]): Paths to the source files (PDF, PNG, JPG, JPEG).
            output_path (str): Destination path for the merged file.
            page_size (str): Target dimensions ("Original", "A4", "Letter", "Legal").
            
        Returns:
            tuple: (bool success_status, str message)
        """
        sizes = {"A4": (595, 842), "Letter": (612, 792), "Legal": (612, 1008)}
        
        try:
            out_doc = fitz.open()
            
            for f in file_paths:
                ext = f.lower().split('.')[-1]
                
                if ext in ['pdf']:
                    temp_doc = fitz.open(f)
                    for p_num in range(len(temp_doc)):
                        orig_page = temp_doc[p_num]
                        target_w, target_h = sizes.get(page_size, (orig_page.rect.width, orig_page.rect.height))
                        
                        new_page = out_doc.new_page(width=target_w, height=target_h)
                        new_page.show_pdf_page(new_page.rect, temp_doc, p_num, keep_proportion=True)
                    temp_doc.close()
                    
                elif ext in ['png', 'jpg', 'jpeg']:
                    img_doc = fitz.open(f)
                    pdf_bytes = img_doc.convert_to_pdf()
                    img_doc.close()
                    
                    temp_pdf = fitz.open("pdf", pdf_bytes)
                    for p_num in range(len(temp_pdf)):
                        orig_page = temp_pdf[p_num]
                        target_w, target_h = sizes.get(page_size, (orig_page.rect.width, orig_page.rect.height))
                        
                        new_page = out_doc.new_page(width=target_w, height=target_h)
                        new_page.show_pdf_page(new_page.rect, temp_pdf, p_num, keep_proportion=True)
                    temp_pdf.close()
            
            # Use tempfile to prevent file locking issues on Windows
            temp_fd, temp_path = tempfile.mkstemp(suffix=".pdf")
            os.close(temp_fd) 
            
            out_doc.save(temp_path)
            out_doc.close()
            
            shutil.copy2(temp_path, output_path)
            os.remove(temp_path)
            
            return True, "Files merged successfully."
            
        except Exception as e:
            return False, f"Error merging files: {str(e)}"

    @staticmethod
    def process_final_pdf(input_path, output_path, pages_string, page_size, rotations, add_logo, add_numbers, apply_compression):
        """
        Executes the final compilation pipeline for the PDF. Handles page extraction, 
        reordering, resizing, individual page rotations, watermarking, pagination, 
        and compression.
        
        Args:
            input_path (str): Path to the source PDF.
            output_path (str): Destination path for the processed PDF.
            pages_string (str): Comma-separated string of pages/ranges to keep (e.g., "1,3,5-7").
            page_size (str): Target dimensions ("Original", "A4", "Letter", "Legal").
            rotations (dict): Dictionary mapping page indices to rotation angles (in degrees).
            add_logo (bool): Whether to apply the centered transparent watermark.
            add_numbers (bool): Whether to append page numbers (e.g., "1 / 5") at the bottom right.
            apply_compression (bool): Whether to apply PyMuPDF garbage collection and deflation.
            
        Returns:
            tuple: (bool success_status, str message)
        """
        try:
            # Parse page ranges
            pages_to_keep = []
            if pages_string.strip():
                parts = pages_string.split(',')
                for part in parts:
                    part = part.strip()
                    if not part: continue
                    if '-' in part:
                        start, end = part.split('-')
                        pages_to_keep.extend(range(int(start) - 1, int(end)))
                    else:
                        pages_to_keep.append(int(part) - 1)
            
            doc = fitz.open(input_path)
            out_doc = fitz.open()
            sizes = {"A4": (595, 842), "Letter": (612, 792), "Legal": (612, 1008)}
            
            if not pages_to_keep:
                pages_to_keep = list(range(len(doc)))

            # ---------------------------------------------------------
            # 1. ORGANIZE, RESIZE, AND EXTRACT PAGES
            # ---------------------------------------------------------
            for idx, p_num in enumerate(pages_to_keep):
                if 0 <= p_num < len(doc):
                    if page_size == "Original" or page_size not in sizes:
                        out_doc.insert_pdf(doc, from_page=p_num, to_page=p_num)
                        new_page = out_doc[-1]
                    else:
                        target_w, target_h = sizes[page_size]
                        new_page = out_doc.new_page(width=target_w, height=target_h)
                        new_page.show_pdf_page(new_page.rect, doc, p_num, keep_proportion=True)
                    
                    rot = rotations.get(idx, 0)
                    if rot != 0:
                        new_page.set_rotation((new_page.rotation + rot) % 360)

            # ---------------------------------------------------------
            # 2. WATERMARK & NUMBERING
            # ---------------------------------------------------------
            logo_path = get_resource_path(os.path.join("assets", "KODAK_LOGO.png"))
            if not os.path.exists(logo_path):
                logo_path = get_resource_path(os.path.join("assets", "KODAK_LOGO"))
            
            total_pages = len(out_doc)
            
            for idx, page in enumerate(out_doc):
                orig_rot = page.rotation
                # Reset rotation temporarily to calculate coordinates reliably
                page.set_rotation(0) 
                
                W = page.rect.width
                H = page.rect.height
                
                # --- Page Numbers ---
                if add_numbers:
                    text_num = f"{idx + 1} / {total_pages}"
                    margin_x, margin_y = 80, 30
                    
                    # Adjust coordinates based on original page rotation
                    if orig_rot == 0: px, py = W - margin_x, H - margin_y
                    elif orig_rot == 90: px, py = W - margin_y, margin_x
                    elif orig_rot == 180: px, py = margin_x, margin_y
                    elif orig_rot == 270: px, py = margin_y, H - margin_x
                        
                    p = fitz.Point(px, py)
                    page.insert_text(p, text_num, fontsize=11, color=(0.3, 0.3, 0.3), rotate=orig_rot)
                
                # --- Watermark (Logo Overlay) ---
                if add_logo:
                    if not os.path.exists(logo_path):
                        raise Exception(f"Logo not found. Make sure the file exists at:\n{logo_path}")
                        
                    # Calculate dimensions relative to rotation to maintain aspect ratio
                    W_vis, H_vis = (H, W) if orig_rot in [90, 270] else (W, H)
                    w_box, h_box = W_vis * 0.6, H_vis * 0.6
                    rect_w, rect_h = (h_box, w_box) if orig_rot in [90, 270] else (w_box, h_box)
                        
                    x_offset = (W - rect_w) / 2
                    y_offset = (H - rect_h) / 2
                    target_rect = fitz.Rect(x_offset, y_offset, x_offset + rect_w, y_offset + rect_h)
                    
                    img_pixmap = fitz.Pixmap(logo_path)
                    
                    # Ensure alpha channel exists for transparency manipulation
                    if img_pixmap.alpha:
                        rgba_pixmap = fitz.Pixmap(fitz.csRGB, img_pixmap)
                    else:
                        temp_rgb = fitz.Pixmap(fitz.csRGB, img_pixmap)
                        rgba_pixmap = fitz.Pixmap(temp_rgb, 1)
                    
                    # Apply 15% opacity globally to the watermark
                    samples = bytearray(rgba_pixmap.samples)
                    for i in range(3, len(samples), 4):
                        samples[i] = int(samples[i] * 0.15) 
                    
                    transparent_pixmap = fitz.Pixmap(fitz.csRGB, rgba_pixmap.w, rgba_pixmap.h, samples, True)
                    page.insert_image(target_rect, pixmap=transparent_pixmap, keep_proportion=True, overlay=True, rotate=orig_rot)

                # Restore original rotation
                page.set_rotation(orig_rot)

            # ---------------------------------------------------------
            # 3. EXPORT & CLEANUP
            # ---------------------------------------------------------
            temp_fd, temp_path = tempfile.mkstemp(suffix=".pdf")
            os.close(temp_fd) 
            
            if apply_compression:
                # garbage=4 (Remove unused objects/streams), deflate=True (Compress streams)
                out_doc.save(temp_path, garbage=4, deflate=True, clean=True)
            else:
                out_doc.save(temp_path)
                
            out_doc.close()
            doc.close() 
            
            shutil.copy2(temp_path, output_path)
            os.remove(temp_path)
            
            return True, "PDF generated and processed successfully."
            
        except Exception as e:
            return False, f"Error processing PDF: {str(e)}"

    @staticmethod
    def remove_metadata(input_path, output_path):
        """
        Strips all embedded metadata (Author, CreationDate, Title, etc.) from the PDF.
        
        Args:
            input_path (str): Path to the source PDF.
            output_path (str): Destination path for the sanitized PDF.
            
        Returns:
            tuple: (bool success_status, str message)
        """
        try:
            doc = fitz.open(input_path)
            doc.set_metadata({}) # Overwrite with empty dict
            
            temp_fd, temp_path = tempfile.mkstemp(suffix=".pdf")
            os.close(temp_fd)
            
            doc.save(temp_path)
            doc.close() 
            
            shutil.copy2(temp_path, output_path)
            os.remove(temp_path)
            return True, "Metadata and hidden data removed successfully."
            
        except Exception as e:
            return False, f"Error cleaning metadata: {str(e)}"

    @staticmethod
    def encrypt_pdf(input_path, output_path, password):
        """
        Applies AES-256 encryption to a PDF document, restricting printing and editing.
        
        Args:
            input_path (str): Path to the source PDF.
            output_path (str): Destination path for the encrypted PDF.
            password (str): Password to secure the document.
            
        Returns:
            tuple: (bool success_status, str message)
        """
        try:
            doc = fitz.open(input_path)
            temp_fd, temp_path = tempfile.mkstemp(suffix=".pdf")
            os.close(temp_fd)
            
            # Allow basic permissions (Print, Copy, Annotate) for authenticated users
            perm = int(fitz.PDF_PERM_PRINT | fitz.PDF_PERM_COPY | fitz.PDF_PERM_ANNOTATE)
            
            doc.save(temp_path, encryption=fitz.PDF_ENCRYPT_AES_256, 
                     user_pw=password, owner_pw=password, permissions=perm)
            doc.close() 
            
            shutil.copy2(temp_path, output_path)
            os.remove(temp_path)
            return True, "Document encrypted and protected successfully."
            
        except Exception as e:
            return False, f"Error encrypting document: {str(e)}"

    @staticmethod
    def decrypt_pdf(input_path, output_path, password):
        """
        Removes encryption from a protected PDF document given the correct password.
        
        Args:
            input_path (str): Path to the encrypted PDF.
            output_path (str): Destination path for the decrypted PDF.
            password (str): The correct password to unlock the document.
            
        Returns:
            tuple: (bool success_status, str message)
        """
        try:
            doc = fitz.open(input_path)
            
            if doc.needs_pass:
                if not doc.authenticate(password):
                    doc.close()
                    return False, "The entered password is incorrect."
                    
            temp_fd, temp_path = tempfile.mkstemp(suffix=".pdf")
            os.close(temp_fd)
            
            # Saving an authenticated doc without encryption arguments exports it unprotected
            doc.save(temp_path)
            doc.close()
            
            shutil.copy2(temp_path, output_path)
            os.remove(temp_path)
            return True, "Protection removed successfully."
            
        except Exception as e:
            return False, f"Error decrypting: {str(e)}"