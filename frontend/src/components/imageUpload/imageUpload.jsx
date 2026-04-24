"use client";

import { useState, useRef, useEffect } from "react";
import { useUploadImageService } from "../../service/ai/useUpload";
import toast from "react-hot-toast";
import "./image.css";

const ImageUpload = ({
  userId,
  image,
  onImageChange,
  setDetectedIngredients,
}) => {
  const [selectedFile, setSelectedFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [detections, setDetections] = useState([]);
  const [originalImageSize, setOriginalImageSize] = useState({
    width: 0,
    height: 0,
  });
  const imageRef = useRef(null);
  const uploadImageService = useUploadImageService();

  // Generate consistent colors for each unique ingredient
  const colorPalette = [
    "#FF6B6B",
    "#4ECDC4",
    "#45B7D1",
    "#FFA07A",
    "#98D8C8",
    "#F7DC6F",
    "#BB8FCE",
    "#85C1E2",
    "#F8B739",
    "#52B788",
    "#FF87AB",
    "#06D6A0",
    "#118AB2",
    "#EF476F",
    "#FFD166",
  ];

  const getColorForLabel = (label, index) => {
    return colorPalette[index % colorPalette.length];
  };

  // Update displayed image size when image loads
  useEffect(() => {
    if (imageRef.current && image) {
      const updateSize = () => {
        // Force re-render when image loads
        setOriginalImageSize((prev) => ({ ...prev }));
      };

      if (imageRef.current.complete) {
        updateSize();
      } else {
        imageRef.current.onload = updateSize;
      }
    }
  }, [image]);

  const handleImageUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      setDetections([]);
      setSelectedFile(file);

      // Get original image dimensions
      const img = new Image();
      img.onload = () => {
        setOriginalImageSize({ width: img.width, height: img.height });
      };

      const reader = new FileReader();
      reader.onloadend = () => {
        img.src = reader.result;
        onImageChange(reader.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSendClick = async () => {
    if (!selectedFile) {
      toast.error("Please select an image first.");
      return;
    }

    if (!userId) {
      toast.error("You must be logged in to upload an image.");
      return;
    }
    try {
      setIsUploading(true);
      const result = await uploadImageService(selectedFile);
      console.log("Upload successful:", result);

      // Store detections from server response
      if (result.detections) {
        setDetections(result.detections);
        setDetectedIngredients(result.detections);
      }

      toast.success("Image uploaded successfully!");
    } catch (error) {
      console.error("Upload failed:", error);
      toast.error("Failed to upload image: " + error.message);
    } finally {
      setIsUploading(false);
    }
  };

  // Calculate scaled bounding box coordinates
  const getScaledBbox = (bbox) => {
    if (!imageRef.current || originalImageSize.width === 0) {
      return { left: 0, top: 0, width: 0, height: 0 };
    }

    const displayedWidth = imageRef.current.offsetWidth;
    const displayedHeight = imageRef.current.offsetHeight;

    const scaleX = displayedWidth / originalImageSize.width;
    const scaleY = displayedHeight / originalImageSize.height;

    const [x1, y1, x2, y2] = bbox;

    return {
      left: x1 * scaleX,
      top: y1 * scaleY,
      width: (x2 - x1) * scaleX,
      height: (y2 - y1) * scaleY,
    };
  };

  return (
    <div className="image-upload-container">
      <input
        type="file"
        accept="image/*"
        onChange={handleImageUpload}
        id="image-input"
        className="image-input"
      />
      <label htmlFor="image-input" className="image-upload-area">
        {image ? (
          <div className="image-container">
            <img
              ref={imageRef}
              src={image}
              alt="Uploaded"
              className="uploaded-image"
            />
            {detections.map((detection, index) => {
              const scaledBbox = getScaledBbox(detection.bbox);
              const color = getColorForLabel(detection.label, index);

              return (
                <div
                  key={index}
                  className="bounding-box"
                  style={{
                    left: `${scaledBbox.left}px`,
                    top: `${scaledBbox.top}px`,
                    width: `${scaledBbox.width}px`,
                    height: `${scaledBbox.height}px`,
                    borderColor: color,
                    backgroundColor: `${color}20`,
                  }}
                >
                  <span
                    className="detection-label"
                    style={{ backgroundColor: color }}
                  >
                    {detection.label} ({Math.round(detection.confidence * 100)}
                    %)
                  </span>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="upload-placeholder">
            <p>INSERT OR TAKE AN IMAGE</p>
            <div className="upload-icons">
              <span className="upload-icon">📁</span>
              <span className="upload-icon">📷</span>
            </div>
          </div>
        )}
      </label>
      <div className="analyze-button-container">
        <button
          className="analyze-btn"
          onClick={handleSendClick}
          disabled={isUploading}
        >
          {isUploading ? "Uploading..." : "SEND"}
        </button>
      </div>
    </div>
  );
};

export default ImageUpload;
