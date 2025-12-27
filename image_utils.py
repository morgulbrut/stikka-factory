"""Image processing and conversion utilities for the Sticker Factory."""

import logging
from PIL import Image, ImageOps

logger = logging.getLogger("sticker_factory.image_utils")


def preper_image(image, label_width):
    """Prepare image by resizing and dithering for thermal printer output."""
    if image.mode == "RGBA":
        background = Image.new("RGBA", image.size, "white")
        image = Image.alpha_composite(background, image)
        image = image.convert("RGB")

    width, height = image.size
    if width != label_width:
        new_height = int((label_width / width) * height)
        image = image.resize((label_width, new_height))
        logger.debug(f"Resizing image from ({width}, {height}) >> {image.size}")

    if image.mode != "L":
        grayscale_image = image.convert("L")
    else:
        grayscale_image = image

    dithered_image = grayscale_image.convert("1", dither=Image.FLOYDSTEINBERG)

    return grayscale_image, dithered_image


def apply_threshold(image, threshold):
    """Apply threshold to convert image to black and white."""
    if image.mode != 'L':
        image = image.convert('L')
    lut = [255 if i > threshold else 0 for i in range(256)]
    return image.point(lut, mode='1')


def resize_image_to_width(image, target_width_mm, label_width, current_dpi=300):
    """Resize image to specific width in millimeters."""
    target_width_inch = target_width_mm / 25.4
    target_width_px = int(target_width_inch * current_dpi)
    current_width = image.width
    scale_factor = target_width_px / current_width
    new_height = int(image.height * scale_factor)
    resized_image = image.resize((target_width_px, new_height), Image.LANCZOS)

    if target_width_px < label_width:
        new_image = Image.new("RGB", (label_width, new_height), (255, 255, 255))
        new_image.paste(resized_image, ((label_width - target_width_px) // 2, 0))
        resized_image = new_image

    logger.debug(f"Image resized from {image.width}x{image.height} to {resized_image.width}x{resized_image.height} pixels.")
    logger.debug(f"Target width was {target_width_mm}mm ({target_width_px}px)")
    return resized_image


def add_border(image, border_width=1):
    """Add a thin black border around the image."""
    if image.mode == '1':
        bordered = Image.new('1', (image.width + 2*border_width, image.height + 2*border_width), 0)
        bordered.paste(image, (border_width, border_width))
        return bordered
    else:
        return ImageOps.expand(image, border=border_width, fill='black')


def apply_levels(image, black_point=0, white_point=255):
    """Apply levels adjustment to an image."""
    if image.mode != 'L':
        image = image.convert('L')
    
    lut = []
    for i in range(256):
        if i <= black_point:
            lut.append(0)
        elif i >= white_point:
            lut.append(255)
        else:
            normalized = (i - black_point) / (white_point - black_point)
            lut.append(int(normalized * 255))
    
    return image.point(lut)


def apply_histogram_equalization(image, black_point=0, white_point=255):
    """Apply histogram equalization with levels adjustment to an image."""
    if image.mode != 'L':
        image = image.convert('L')
    
    leveled = apply_levels(image, black_point, white_point)
    return ImageOps.equalize(leveled)


def img_concat_v(im1, im2, image_width):
    """Vertically concatenate two images."""
    logger.debug(f"Concatenating images vertically: im1 size {im1.size}, im2 size {im2.size}, target width {image_width}")
    dst = Image.new("RGB", (im1.width, im1.height + image_width))
    dst.paste(im1, (0, 0))
    im2 = im2.resize((image_width, image_width))
    dst.paste(im2, (0, im1.height))
    logger.debug(f"Resulting image size: {dst.size}")
    logger.debug(dst)   
    return dst


def determine_tile_rows(image, label_width):
    """
    Always return 2 rows to save paper.
    """
    return 2


def split_image_into_tiles(image, label_width, num_rows):
    """
    Split an image into tiles for printing across multiple labels.
    
    Args:
        image: PIL Image to split
        label_width: Width of each label in pixels
        num_rows: Number of rows (2 or 3)
    
    Returns:
        List of PIL Images, one for each tile
    """
    # Convert RGBA to RGB if needed
    if image.mode == "RGBA":
        background = Image.new("RGBA", image.size, "white")
        image = Image.alpha_composite(background, image)
        image = image.convert("RGB")
    
    # Resize image to label width, maintaining aspect ratio
    width, height = image.size
    if width != label_width:
        new_height = int((label_width / width) * height)
        image = image.resize((label_width, new_height), Image.LANCZOS)
        logger.debug(f"Resized image to {label_width}x{new_height} for tiling")
    
    width, height = image.size
    
    # Calculate tile height
    tile_height = height // num_rows
    remainder = height % num_rows
    
    tiles = []
    y_offset = 0
    
    for i in range(num_rows):
        # Add remainder to the last tile
        current_tile_height = tile_height + (remainder if i == num_rows - 1 else 0)
        
        # Extract tile
        tile = image.crop((0, y_offset, width, y_offset + current_tile_height))
        tiles.append(tile)
        
        y_offset += current_tile_height
        logger.debug(f"Created tile {i+1}/{num_rows}: {tile.size}")
    
    return tiles


def create_tile_preview(tiles, label_width):
    """
    Create a preview image showing all tiles arranged in a grid.
    
    Args:
        tiles: List of PIL Images (tiles)
        label_width: Width of each label in pixels
    
    Returns:
        PIL Image showing all tiles in a grid layout
    """
    num_tiles = len(tiles)
    
    # Calculate preview dimensions
    # Scale down tiles for preview (max 300px wide per tile)
    preview_scale = min(1.0, 300 / label_width)
    preview_tile_width = int(label_width * preview_scale)
    
    # Find max tile height for preview
    max_tile_height = max(tile.height for tile in tiles)
    preview_tile_height = int(max_tile_height * preview_scale)
    
    # Create preview image
    # Arrange tiles in a single column for preview
    preview_width = preview_tile_width
    preview_height = preview_tile_height * num_tiles + (10 * (num_tiles - 1))  # 10px spacing between tiles
    
    preview = Image.new("RGB", (preview_width, preview_height), "white")
    
    y_offset = 0
    for i, tile in enumerate(tiles):
        # Resize tile for preview
        tile_preview = tile.resize((preview_tile_width, int(tile.height * preview_scale)), Image.LANCZOS)
        preview.paste(tile_preview, (0, y_offset))
        y_offset += tile_preview.height + 10  # Add spacing
    
    logger.debug(f"Created preview image: {preview.size}")
    return preview
