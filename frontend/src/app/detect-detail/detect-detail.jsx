import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import "./detect-detail.css";
import { useGetDetectDetail } from "../../service/user/useDetectService";

// Simple encoding/decoding functions
const encodeId = (id) => {
  const SECRET = 12345;
  return (id ^ SECRET).toString(36);
};

const decodeId = (encoded) => {
  const SECRET = 12345;
  return parseInt(encoded, 36) ^ SECRET;
};

const DetectionDetail = () => {
  const { encodedId } = useParams();
  const navigate = useNavigate();
  const [detection, setDetection] = useState(null);
  const [recommendation, setRecommendation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const getDetectDetail = useGetDetectDetail();

  console.log("Encoded ID from URL:", encodedId);

  useEffect(() => {
    const fetchDetection = async () => {
      try {
        setLoading(true);
        const detectId = decodeId(encodedId);

        console.log("Decoded Detection ID:", detectId);

        const response = await getDetectDetail(detectId);

        if (!response) {
          throw new Error("Detection not found");
        }

        setDetection(response);

        // Parse the recommendation JSON string
        if (response.recommendation) {
          try {
            const parsed = JSON.parse(response.recommendation);
            setRecommendation(parsed);
          } catch (parseError) {
            console.error("Error parsing recommendation:", parseError);
            setRecommendation(null);
          }
        }
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchDetection();
  }, [encodedId, getDetectDetail]);

  const handleBack = () => {
    navigate(-1);
  };

  if (loading) {
    return (
      <div className="detection-detail">
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>Loading detection...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="detection-detail">
        <div className="error-container">
          <h2>Error</h2>
          <p>{error}</p>
          <button onClick={handleBack} className="btn-back">
            Go Back
          </button>
        </div>
      </div>
    );
  }

  if (!detection) {
    return null;
  }

  return (
    <div className="detection-detail">
      <div className="detail-container">
        <button onClick={handleBack} className="btn-back">
          ← Back to Detections
        </button>

        <div className="detail-content">
          {/* Detected Ingredients Section */}
          <div className="ingredients-block">
            <h2>Detected Ingredients</h2>
            {detection.detected_ingredients &&
            detection.detected_ingredients.length > 0 ? (
              <div className="ingredients-grid">
                {Object.entries(
                  detection.detected_ingredients.reduce((acc, ingredient) => {
                    acc[ingredient] = (acc[ingredient] || 0) + 1;
                    return acc;
                  }, {})
                ).map(([ingredient, count], index) => (
                  <div key={index} className="ingredient-tag">
                    {ingredient} {count > 1 && `(${count})`}
                  </div>
                ))}
              </div>
            ) : (
              <p className="no-data">No ingredients detected</p>
            )}
          </div>

          {/* Recommendation Section */}
          {recommendation ? (
            <div className="recommendation-block">
              <h2>Recipe Recommendation: {recommendation.dish_name}</h2>

              {/* Recipe Info */}
              <div className="recipe-info">
                <div className="info-item">
                  <span className="info-label">⏱️ Prep Time:</span>
                  <span className="info-value">
                    {recommendation.time?.prep}
                  </span>
                </div>
                <div className="info-item">
                  <span className="info-label">🔥 Cook Time:</span>
                  <span className="info-value">
                    {recommendation.time?.cook}
                  </span>
                </div>
                <div className="info-item">
                  <span className="info-label">⏰ Total Time:</span>
                  <span className="info-value">
                    {recommendation.time?.total}
                  </span>
                </div>
                <div className="info-item">
                  <span className="info-label">👥 Servings:</span>
                  <span className="info-value">
                    {recommendation.servings} người
                  </span>
                </div>
              </div>

              {/* Needed Ingredients */}
              {recommendation.ingredients?.needed &&
                recommendation.ingredients.needed.length > 0 && (
                  <div className="needed-ingredients">
                    <h3>Cần mua thêm:</h3>
                    <div className="ingredients-grid">
                      {recommendation.ingredients.needed.map((item, index) => (
                        <span key={index} className="needed-tag">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

              {/* Preparation */}
              {recommendation.preparation &&
                recommendation.preparation.length > 0 && (
                  <div className="preparation-section">
                    <h3>Chuẩn bị:</h3>
                    <ul className="preparation-list">
                      {recommendation.preparation.map((step, index) => (
                        <li key={index}>{step}</li>
                      ))}
                    </ul>
                  </div>
                )}

              {/* Cooking Steps */}
              {recommendation.steps && recommendation.steps.length > 0 && (
                <div className="steps-section">
                  <h3>Các bước thực hiện:</h3>
                  <div className="steps-list">
                    {recommendation.steps.map((step, index) => (
                      <div key={index} className="step-item">
                        <div className="step-number">{index + 1}</div>
                        <div className="step-content">
                          {step.replace(/^Bước \d+:\s*/, "")}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Tips */}
              {recommendation.tips && recommendation.tips.length > 0 && (
                <div className="tips-section">
                  <h3>💡 Mẹo hay:</h3>
                  <ul className="tips-list">
                    {recommendation.tips.map((tip, index) => (
                      <li key={index}>{tip}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Nutrition */}
              {recommendation.nutrition && (
                <div className="nutrition-section">
                  <h3>Thông tin dinh dưỡng (1 phần):</h3>
                  <div className="nutrition-grid">
                    <div className="nutrition-item">
                      <span className="nutrition-value">
                        {recommendation.nutrition.calories}
                      </span>
                      <span className="nutrition-label">Calories</span>
                    </div>
                    <div className="nutrition-item">
                      <span className="nutrition-value">
                        {recommendation.nutrition.protein}
                      </span>
                      <span className="nutrition-label">Protein</span>
                    </div>
                    <div className="nutrition-item">
                      <span className="nutrition-value">
                        {recommendation.nutrition.carbohydrate}
                      </span>
                      <span className="nutrition-label">Carbs</span>
                    </div>
                    <div className="nutrition-item">
                      <span className="nutrition-value">
                        {recommendation.nutrition.fat}
                      </span>
                      <span className="nutrition-label">Fat</span>
                    </div>
                    <div className="nutrition-item">
                      <span className="nutrition-value">
                        {recommendation.nutrition.fiber}
                      </span>
                      <span className="nutrition-label">Fiber</span>
                    </div>
                  </div>
                  {recommendation.nutrition.vitamins && (
                    <p className="vitamins-info">
                      <strong>Vitamins:</strong>{" "}
                      {recommendation.nutrition.vitamins}
                    </p>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="recommendation-block">
              <h2>Recommendation</h2>
              <p className="no-data">No recommendation available</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export { encodeId, decodeId };
export default DetectionDetail;
