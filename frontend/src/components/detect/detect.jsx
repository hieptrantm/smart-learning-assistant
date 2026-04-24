import "./detect.css";
import { useEffect, useState } from "react";
import ImageUpload from "../imageUpload/imageUpload";
import { useStartAgentService } from "../../service/agent/useAgent.js";
import { ChefHat } from "lucide-react";
import toast from "react-hot-toast";

const Detect = ({ user }) => {
  const [uploadedImage, setUploadedImage] = useState(null);
  const [backendInfo, setBackendInfo] = useState("");
  const [detectedIngredients, setDetectedIngredients] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const startAgentService = useStartAgentService();

  const handleCookForMe = async () => {
    if (!user?.email || !user?.email_verified) {
      toast.error("You must be logged in and have a verified email.");
      return;
    }

    if (detectedIngredients.length === 0) {
      toast.error("No detected ingredients to cook with.");
      return;
    }
    try {
      setIsUploading(true);
      const response = await startAgentService({
        detected_ingredients: detectedIngredients,
      });

      if (!response && !response.ok) {
        toast.error("Failed to start cooking agent.");
        throw new Error("Failed to start cooking agent.");
      }

      toast.success("Cooking agent started! Check your email soon.");
    } catch (error) {
      toast.error("Failed to start cooking agent.");
    } finally {
      setIsUploading(false);
    }
  };

  useEffect(() => {
    if (detectedIngredients.length > 0) {
      // Count occurrences by label only
      const counts = detectedIngredients.reduce((acc, item) => {
        const label = item.label;
        acc[label] = (acc[label] || 0) + 1;
        return acc;
      }, {});

      const info =
        "Detected ingredients: " +
        Object.entries(counts)
          .map(([key, value]) => `${key} (${value})`)
          .join(", ");

      console.log("detected ingredients: ", detectedIngredients);
      setBackendInfo(info);
    }
  }, [detectedIngredients]);

  return (
    <div className="detect">
      <ImageUpload
        userId={user?.id}
        image={uploadedImage}
        onImageChange={setUploadedImage}
        setDetectedIngredients={setDetectedIngredients}
      />

      <div className="info-section">
        <div className="info-row">
          <textarea
            className="info-field"
            value={backendInfo}
            onChange={(e) => setBackendInfo(e.target.value)}
            placeholder="Detected ingredients will appear here..."
            readOnly
            rows={3}
          />
          <button
            className="cook-button"
            onClick={handleCookForMe}
            disabled={isUploading}
          >
            <ChefHat size={20} />
            <span className="cook-button-text">
              {isUploading ? "Cooking..." : "Cook something for me!"}
            </span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default Detect;
