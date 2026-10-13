"""Grad-CAM heatmap: which parts of the leaf pushed the model toward its answer.

Uses pytorch-grad-cam on ONE model of the ensemble (the first CNN, normally EfficientNetV2-S),
because running Grad-CAM on every model is slow on a free CPU. The heatmap therefore explains
that model's reasoning, not the whole ensemble's.
"""
import numpy as np
import torch
from PIL import Image


def pick_target_layer(model):
    """Return (layer, reshape_transform) for the last convolutional/attention stage, or None if unsupported."""
    if hasattr(model, "layers") and hasattr(model, "patch_embed") and hasattr(model, "head"):  # Swin
        # timm >= 0.9 Swin keeps feature maps as (B, H, W, C); Grad-CAM wants (B, C, H, W).
        return model.layers[-1].blocks[-1].norm1, lambda t: t.permute(0, 3, 1, 2)
    if hasattr(model, "blocks") and hasattr(model, "conv_head"):                      # EfficientNet family
        return model.blocks[-1], None
    if hasattr(model, "layer4"):                                                       # ResNet family
        return model.layer4[-1], None
    return None


def is_supported(model) -> bool:
    return pick_target_layer(model) is not None


def heatmap_overlay(model, x: torch.Tensor, class_idx: int, rgb_uint8: np.ndarray) -> Image.Image:
    """x: normalised input (1,3,S,S). rgb_uint8: the same image, un-normalised (S,S,3). Returns the overlay."""
    # Imported here so that a problem with this library only costs the heatmap, never the diagnosis.
    from pytorch_grad_cam import GradCAM
    from pytorch_grad_cam.utils.image import show_cam_on_image
    from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget

    layer, reshape = pick_target_layer(model)
    model.eval()
    with torch.enable_grad():
        with GradCAM(model=model, target_layers=[layer], reshape_transform=reshape) as cam:
            grayscale = cam(input_tensor=x, targets=[ClassifierOutputTarget(class_idx)])[0]
    overlay = show_cam_on_image(rgb_uint8.astype(np.float32) / 255.0, grayscale, use_rgb=True, image_weight=0.55)
    return Image.fromarray(overlay)
