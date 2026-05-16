from PIL import Image
import numpy as np

# Load scrambled image
img = Image.open("GA0/jigsaw.webp").convert("RGB")

# Grid size
GRID = 5

# Tile size
w, h = img.size
tile_w = w // GRID
tile_h = h // GRID

# Mapping:
# (scrambled_row, scrambled_col) -> (original_row, original_col)
mapping = {
    (0, 0): (2, 1),
    (0, 1): (1, 1),
    (0, 2): (4, 1),
    (0, 3): (0, 3),
    (0, 4): (0, 1),

    (1, 0): (1, 4),
    (1, 1): (2, 0),
    (1, 2): (2, 4),
    (1, 3): (4, 2),
    (1, 4): (2, 2),

    (2, 0): (0, 0),
    (2, 1): (3, 2),
    (2, 2): (4, 3),
    (2, 3): (3, 0),
    (2, 4): (3, 4),

    (3, 0): (1, 0),
    (3, 1): (2, 3),
    (3, 2): (3, 3),
    (3, 3): (4, 4),
    (3, 4): (0, 2),

    (4, 0): (3, 1),
    (4, 1): (1, 2),
    (4, 2): (1, 3),
    (4, 3): (0, 4),
    (4, 4): (4, 0),
}

# Create empty reconstructed image
reconstructed = Image.new("RGB", (w, h))

# Reassemble tiles
for (sr, sc), (orow, ocol) in mapping.items():
    # Source tile coordinates
    left = sc * tile_w
    upper = sr * tile_h
    right = left + tile_w
    lower = upper + tile_h

    tile = img.crop((left, upper, right, lower))

    # Destination coordinates
    dst_left = ocol * tile_w
    dst_upper = orow * tile_h

    reconstructed.paste(tile, (dst_left, dst_upper))

# Convert to numpy array
arr = np.array(reconstructed).astype(np.float32)

# Luminance grayscale conversion
gray = (
    0.2126 * arr[:, :, 0] +
    0.7152 * arr[:, :, 1] +
    0.0722 * arr[:, :, 2]
)

# Convert back to uint8
gray = np.clip(gray, 0, 255).astype(np.uint8)

# Create grayscale RGB image
gray_img = Image.fromarray(gray, mode="L")

# Save losslessly
gray_img.save("reconstructed_grayscale.png")

print("Saved: reconstructed_grayscale.png")