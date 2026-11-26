"""Bounded local image-quality metrics with explicit reference evidence.

Only RGB8 PNG rasters decoded by image_structure are supported. All image
observations are caller-supplied local paths, NOT independently authenticated.
"""
from .image_structure import png_grayscale_pixels

def _laplacian_variance(width, height, pixels):
    """Population variance of the 4-neighbor Laplacian on interior pixels.

    Pixels are BT.601 integer grayscale 0..255; boundaries are excluded.
    The versioned convention uses central coefficient +4, neighbor -1 and
    population variance, with no clipping, rescaling or normalization.
    """
    if width < 3 or height < 3 or len(pixels) != width * height:
        raise ValueError("Insufficient raster for Laplacian variance")
    count = (width - 2) * (height - 2)
    sum_value = 0
    sum_squares = 0
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            at = y * width + x
            value = (4 * pixels[at] - pixels[at - width]
                     - pixels[at + width] - pixels[at - 1]
                     - pixels[at + 1])
            sum_value += value
            sum_squares += value * value
    # Exact nonnegative numerator scaled by count^2.
    return sum_squares * count - sum_value * sum_value, count * count


def blur_score_ratio(reference_path, candidate_path):
    """Return reference/candidate focus variance ratio as two integer pairs.

    Comparison avoids floats and undefined zero-variance division. All input
    image dimensions must match exactly. The caller applies a chosen ratio
    threshold; this helper does not choose a policy value.
    """
    rw, rh, rp = png_grayscale_pixels(reference_path)
    cw, ch, cp = png_grayscale_pixels(candidate_path)
    if (rw, rh) != (cw, ch):
        raise ValueError("Unaligned raster dimensions")
    ref_num, ref_den = _laplacian_variance(rw, rh, rp)
    cand_num, cand_den = _laplacian_variance(cw, ch, cp)
    if ref_num == 0 and cand_num == 0:
        raise ValueError("Both images lack measurable Laplacian variance")
    return ref_num, ref_den, cand_num, cand_den


SSIM_ALGORITHM_ID = "ssim-skimage-v1"


def local_ssim(reference_path, candidate_path):
    """Pinned scikit-image grayscale SSIM over aligned RGB8 PNG rasters.

    Mandatory configuration: scikit-image 0.26.0, NumPy 2.3.5,
    SciPy 1.16.3; win_size=7, gaussian_weights=False,
    use_sample_covariance=True, channel_axis=None, data_range=255.
    The input is the same BT.601 integer grayscale as the blur metric.
    Runtime libraries are optional; absent or incompatible versions abstain.
    """
    try:
        import numpy as np
        import scipy
        import skimage
        from skimage.metrics import structural_similarity
    except ImportError as error:
        raise ValueError("Pinned SSIM libraries unavailable") from error
    if (np.__version__ != "2.3.5" or scipy.__version__ != "1.16.3"
            or skimage.__version__ != "0.26.0"):
        raise ValueError("Unverified SSIM numerical runtime versions")
    rw, rh, rp = png_grayscale_pixels(reference_path)
    cw, ch, cp = png_grayscale_pixels(candidate_path)
    if (rw, rh) != (cw, ch) or min(rw, rh) < 7:
        raise ValueError("SSIM requires matching at least 7x7 rasters")
    ref = np.asarray(rp, dtype=np.uint8).reshape((rh, rw))
    cand = np.asarray(cp, dtype=np.uint8).reshape((ch, cw))
    score = float(structural_similarity(
        ref, cand,
        win_size=7,
        gaussian_weights=False,
        use_sample_covariance=True,
        data_range=255,
        channel_axis=None,
    ))
    if not np.isfinite(score) or score < -1 or score > 1:
        raise ValueError("Undefined SSIM measurement")
    return score
