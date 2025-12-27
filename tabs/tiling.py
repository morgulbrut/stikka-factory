"""Tiling tab content - split images into multiple label rows."""

import logging
import streamlit as st
import os
import io
from PIL import Image

logger = logging.getLogger("sticker_factory.tabs.tiling")


def fetch_image_from_url(url):
    """Validate and fetch image from URL."""
    if not url.startswith('https://'):
        st.error('Only HTTPS URLs are allowed for security')
        return None
        
    try:
        import requests
        from io import BytesIO
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Verify content type is an image
        content_type = response.headers.get('content-type', '')
        if not content_type.startswith('image/'):
            st.error('URL does not point to a valid image')
            return None
            
        return Image.open(BytesIO(response.content)).convert("RGB")
    except Exception as e:
        st.error(f'Error fetching image: {str(e)}')
        return None


def render(preper_image, print_image, printer_info, determine_tile_rows, split_image_into_tiles, create_tile_preview):
    """Render the Tiling tab."""
    st.subheader(":printer: tiling mode")
    st.markdown("Upload an image to split it into 2 rows of labels")

    label_width = printer_info['label_width']
    
    # Allow the user to upload an image or PDF
    uploaded_image = st.file_uploader(
        "Choose an image file or PDF to tile", 
        type=["png", "jpg", "jpeg", "gif", "webp", "pdf"],
        key="tiling_file_uploader"
    )
    
    # Or fetch from URL
    image_url = st.text_input("Or enter an HTTPS image URL to fetch and tile", key="tiling_url")
    
    # Process uploaded file or URL
    image_to_process = None
    
    if uploaded_image is not None:
        # Handle PDF files
        if uploaded_image.type == "application/pdf":
            try:
                import fitz  # PyMuPDF
                
                st.info("PDF file detected. Converting the first page to an image.")
                dpi_selected = st.selectbox("Select the DPI for the conversion", [72, 92, 150, 300, 600], index=1, key="tiling_pdf_dpi")
                
                # Open the PDF file
                pdf_document = fitz.open(stream=uploaded_image.read(), filetype="pdf")
                
                # Convert the first page to an image
                page = pdf_document.load_page(0)
                pix = page.get_pixmap(dpi=dpi_selected)
                image_to_process = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                
            except ImportError:
                st.error("PyMuPDF (fitz) is not installed. Install it with: pip install pymupdf")
                st.stop()
            except Exception as e:
                st.error(f"Error converting PDF: {str(e)}")
                st.stop()
        else:
            # Convert the uploaded file to a PIL Image
            image_to_process = Image.open(uploaded_image).convert("RGB")
    
    elif image_url:
        # Try to fetch and process image from URL
        image_to_process = fetch_image_from_url(image_url)
    
    if image_to_process:
        # Determine number of rows based on aspect ratio
        num_rows = determine_tile_rows(image_to_process, label_width)
        
        st.info(f"Image will be split into **{num_rows} rows** of labels")
        
        # Split image into tiles
        tiles = split_image_into_tiles(image_to_process, label_width, num_rows)
        
        # Create and show preview
        preview_image = create_tile_preview(tiles, label_width)
        st.image(preview_image, caption=f"Preview: {num_rows} tiles arranged vertically", use_container_width=True)
        
        # Show individual tiles in columns
        st.subheader("Individual Tiles")
        cols = st.columns(num_rows)
        for i, (col, tile) in enumerate(zip(cols, tiles)):
            with col:
                st.image(tile, caption=f"Tile {i+1}/{num_rows} ({tile.width}x{tile.height}px)", use_container_width=True)
        
        # Print options
        st.subheader("Print Options")
        dither_checkbox = st.checkbox(
            "Dither - _use for high detail, true by default_", 
            value=True,
            key="tiling_dither"
        )
        
        # Print all tiles button
        button_text = "Print All Tiles (Rotated 90°)"
        if dither_checkbox:
            button_text += " (Dithered)"
        
        if st.button(button_text, key="tiling_print_all", type="primary"):
            rotate_value = 90  # Always rotate 90 degrees
            dither_value = dither_checkbox
            
            st.info(f"Printing {len(tiles)} tiles...")
            success_count = 0
            
            for i, tile in enumerate(tiles):
                with st.spinner(f"Printing tile {i+1}/{len(tiles)}..."):
                    # Prepare the tile for printing
                    prepared_tile = tile.copy()
                    success = print_image(
                        prepared_tile, 
                        printer_info=printer_info, 
                        rotate=rotate_value, 
                        dither=dither_value
                    )
                    if success:
                        success_count += 1
                    else:
                        st.warning(f"Failed to print tile {i+1}")
            
            if success_count == len(tiles):
                st.success(f"Successfully printed all {len(tiles)} tiles!")
            else:
                st.warning(f"Printed {success_count}/{len(tiles)} tiles successfully.")
        
        # Option to print individual tiles
        st.subheader("Print Individual Tiles")
        tile_cols = st.columns(num_rows)
        for i, (col, tile) in enumerate(zip(tile_cols, tiles)):
            with col:
                if st.button(f"Print Tile {i+1}", key=f"tiling_print_{i}"):
                    rotate_value = 90  # Always rotate 90 degrees
                    dither_value = dither_checkbox
                    with st.spinner(f"Printing tile {i+1}..."):
                        print_image(
                            tile, 
                            printer_info=printer_info, 
                            rotate=rotate_value, 
                            dither=dither_value
                        )
                    st.success(f"Tile {i+1} sent to printer!")

