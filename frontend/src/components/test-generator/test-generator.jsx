import { useState } from "react";
import "./test-generator.css";
import {
  FileText,
  Play,
  CheckCircle2,
  Award,
  Brain,
  BarChart3,
  Clock,
  Zap,
  AlertCircle,
} from "lucide-react";

const TestGenerator = ({ user }) => {
  const [testType, setTestType] = useState("multiple-choice");
  const [difficulty, setDifficulty] = useState("medium");
  const [numQuestions, setNumQuestions] = useState(10);
  const [selectedSubject, setSelectedSubject] = useState("");
  const [showResults, setShowResults] = useState(false);
  const [answers, setAnswers] = useState({});

  // Sample test data
  const sampleQuestions = [
    {
      id: 1,
      question: "Tích phân xác định của hàm f(x) = 2x trên đoạn [0, 3] bằng?",
      type: "multiple-choice",
      options: ["A. 6", "B. 9", "C. 12", "D. 3"],
      correct: 1,
      difficulty: "easy",
      topic: "Tích phân",
      explanation: "∫₀³ 2x dx = [x²]₀³ = 9 - 0 = 9",
    },
    {
      id: 2,
      question: "Đạo hàm của hàm số y = ln(x² + 1) là?",
      type: "multiple-choice",
      options: ["A. 2x/(x²+1)", "B. 1/(x²+1)", "C. 2x·ln(x²+1)", "D. x/(x²+1)"],
      correct: 0,
      difficulty: "medium",
      topic: "Đạo hàm",
      explanation: "Áp dụng quy tắc đạo hàm hàm hợp: y' = (2x)/(x² + 1)",
    },
    {
      id: 3,
      question: "Ma trận đơn vị cấp 3 có bao nhiêu phần tử bằng 1?",
      type: "multiple-choice",
      options: ["A. 1", "B. 3", "C. 6", "D. 9"],
      correct: 1,
      difficulty: "easy",
      topic: "Đại số tuyến tính",
      explanation: "Ma trận đơn vị cấp n có n phần tử bằng 1 trên đường chéo chính.",
    },
  ];

  const pastTests = [
    { id: 1, name: "Kiểm tra Chương 5 - Tích phân", date: "28/02/2026", score: 85, total: 100, questions: 20, time: "30 phút", subject: "Toán cao cấp" },
    { id: 2, name: "Quiz Vật lý - Điện từ", date: "27/02/2026", score: 72, total: 100, questions: 15, time: "25 phút", subject: "Vật lý" },
    { id: 3, name: "Python OOP Quiz", date: "26/02/2026", score: 95, total: 100, questions: 10, time: "20 phút", subject: "Lập trình Python" },
  ];

  const strengthAnalysis = [
    { topic: "Tích phân", score: 90, level: "strong" },
    { topic: "Đạo hàm", score: 85, level: "strong" },
    { topic: "Đại số tuyến tính", score: 65, level: "medium" },
    { topic: "Giải tích hàm nhiều biến", score: 45, level: "weak" },
    { topic: "Phương trình vi phân", score: 55, level: "weak" },
  ];

  const handleAnswer = (questionId, optionIdx) => {
    setAnswers((prev) => ({ ...prev, [questionId]: optionIdx }));
  };

  return (
    <div className="test-generator">
      {/* Header */}
      <div className="test-header">
        <div className="test-header-left">
          <h1>
            <FileText size={28} /> Test Generator & Grading
          </h1>
          <p>Tạo bài kiểm tra tự động theo cấp độ, đánh giá và phân tích kết quả</p>
        </div>
      </div>

      <div className="test-layout">
        {/* Test Creation Panel */}
        <div className="test-create-panel">
          <h2 className="panel-title">
            <Zap size={18} /> Tạo bài kiểm tra mới
          </h2>

          <div className="test-form">
            <div className="form-group">
              <label>Môn học</label>
              <select
                value={selectedSubject}
                onChange={(e) => setSelectedSubject(e.target.value)}
              >
                <option value="">Chọn môn học...</option>
                <option value="math">Toán cao cấp</option>
                <option value="physics">Vật lý đại cương</option>
                <option value="python">Lập trình Python</option>
                <option value="english">Tiếng Anh B2</option>
              </select>
            </div>

            <div className="form-group">
              <label>Loại câu hỏi</label>
              <div className="radio-group">
                <label className={`radio-option ${testType === "multiple-choice" ? "radio-active" : ""}`}>
                  <input type="radio" name="type" value="multiple-choice" checked={testType === "multiple-choice"} onChange={(e) => setTestType(e.target.value)} />
                  <CheckCircle2 size={16} /> Trắc nghiệm
                </label>
                <label className={`radio-option ${testType === "essay" ? "radio-active" : ""}`}>
                  <input type="radio" name="type" value="essay" checked={testType === "essay"} onChange={(e) => setTestType(e.target.value)} />
                  <FileText size={16} /> Tự luận
                </label>
                <label className={`radio-option ${testType === "mixed" ? "radio-active" : ""}`}>
                  <input type="radio" name="type" value="mixed" checked={testType === "mixed"} onChange={(e) => setTestType(e.target.value)} />
                  <Brain size={16} /> Kết hợp
                </label>
              </div>
            </div>

            <div className="form-group">
              <label>Cấp độ</label>
              <div className="difficulty-options">
                {["easy", "medium", "hard", "mixed"].map((d) => (
                  <button
                    key={d}
                    className={`difficulty-btn difficulty-${d} ${difficulty === d ? "difficulty-active" : ""}`}
                    onClick={() => setDifficulty(d)}
                  >
                    {d === "easy" ? "Dễ" : d === "medium" ? "Trung bình" : d === "hard" ? "Khó" : "Tổng hợp"}
                  </button>
                ))}
              </div>
            </div>

            <div className="form-group">
              <label>Số câu hỏi: {numQuestions}</label>
              <input
                type="range"
                min="5"
                max="50"
                value={numQuestions}
                onChange={(e) => setNumQuestions(e.target.value)}
                className="range-input"
              />
              <div className="range-labels">
                <span>5</span>
                <span>50</span>
              </div>
            </div>

            <button className="generate-btn">
              <Play size={18} /> Tạo bài kiểm tra
            </button>
          </div>

          {/* Sample Preview */}
          <div className="test-preview">
            <h3>Xem trước ({sampleQuestions.length} câu mẫu)</h3>
            {sampleQuestions.map((q, idx) => (
              <div className="preview-question" key={q.id}>
                <div className="question-header">
                  <span className="question-num">Câu {idx + 1}</span>
                  <span className={`question-diff diff-${q.difficulty}`}>
                    {q.difficulty === "easy" ? "Dễ" : q.difficulty === "medium" ? "Trung bình" : "Khó"}
                  </span>
                </div>
                <p className="question-text-content">{q.question}</p>
                <div className="question-options">
                  {q.options.map((opt, oidx) => (
                    <label
                      key={oidx}
                      className={`option-label ${answers[q.id] === oidx ? "option-selected" : ""} ${showResults ? (oidx === q.correct ? "option-correct" : answers[q.id] === oidx ? "option-wrong" : "") : ""}`}
                      onClick={() => !showResults && handleAnswer(q.id, oidx)}
                    >
                      <span className="option-marker">{String.fromCharCode(65 + oidx)}</span>
                      {opt.substring(3)}
                    </label>
                  ))}
                </div>
                {showResults && (
                  <div className="question-explanation">
                    <AlertCircle size={14} />
                    <span>{q.explanation}</span>
                  </div>
                )}
              </div>
            ))}
            <button className="submit-test-btn" onClick={() => setShowResults(!showResults)}>
              {showResults ? "Ẩn đáp án" : "Nộp bài & Xem đáp án"}
            </button>
          </div>
        </div>

        {/* Right Panel - Results & Analysis */}
        <div className="test-results-panel">
          {/* Past Tests */}
          <div className="results-section">
            <h2 className="panel-title">
              <Award size={18} /> Lịch sử kiểm tra
            </h2>
            <div className="past-tests">
              {pastTests.map((test) => (
                <div className="past-test-card" key={test.id}>
                  <div className="past-test-info">
                    <span className="past-test-name">{test.name}</span>
                    <span className="past-test-meta">
                      <Clock size={12} /> {test.date} • {test.questions} câu • {test.time}
                    </span>
                  </div>
                  <div className={`past-test-score ${test.score >= 80 ? "score-high" : test.score >= 60 ? "score-mid" : "score-low"}`}>
                    {test.score}%
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Strength Analysis */}
          <div className="results-section">
            <h2 className="panel-title">
              <BarChart3 size={18} /> Phân tích điểm mạnh/yếu
            </h2>
            <div className="strength-list">
              {strengthAnalysis.map((item, idx) => (
                <div className="strength-item" key={idx}>
                  <div className="strength-header">
                    <span className="strength-topic">{item.topic}</span>
                    <span className={`strength-score strength-${item.level}`}>{item.score}%</span>
                  </div>
                  <div className="strength-bar">
                    <div
                      className={`strength-fill strength-fill-${item.level}`}
                      style={{ width: `${item.score}%` }}
                    ></div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Adaptive Learning Note */}
          <div className="adaptive-note">
            <Brain size={20} />
            <div>
              <strong>Adaptive Learning</strong>
              <p>LLM tự động điều chỉnh tiến độ học tập dựa trên kết quả kiểm tra. Các chủ đề yếu sẽ được ưu tiên ôn tập trong Study Planner.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TestGenerator;
