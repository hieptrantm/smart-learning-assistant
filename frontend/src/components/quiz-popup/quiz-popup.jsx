import { useState, useCallback } from "react";
import "./quiz-popup.css";

// Question type IDs (must match backend ETypeQuestion enum)
const ETypeQuestion = {
  MULTIPLE_CHOICE: 1,
  FILL_IN_BLANK: 2,
  TRUE_FALSE: 3,
  SHORT_ANSWER: 4,
};

const QuizPopup = ({ questions, subjectName, targetGrade, onClose, onFinish, evaluateAnswer }) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [results, setResults] = useState({});
  const [textInputs, setTextInputs] = useState({});
  const [evaluating, setEvaluating] = useState({});
  const [showSummary, setShowSummary] = useState(false);

  const currentQuestion = questions[currentIndex];
  const totalQuestions = questions.length;

  // Handle multiple_choice / true_false selection
  const handleOptionSelect = useCallback((questionIdx, optionIdx) => {
    if (results[questionIdx] !== undefined) return;

    const q = questions[questionIdx];
    setAnswers((prev) => ({ ...prev, [questionIdx]: optionIdx }));

    // Types 1 (MULTIPLE_CHOICE) and 3 (TRUE_FALSE): evaluate immediately by checking isCorrect
    const qType = q.type || q.question_type;
    if (qType === ETypeQuestion.MULTIPLE_CHOICE || qType === ETypeQuestion.TRUE_FALSE) {
      const correctIdx = q.options?.findIndex((o) => o.isCorrect === true || o.is_correct === true);
      const isCorrect = optionIdx === correctIdx;
      setResults((prev) => ({
        ...prev,
        [questionIdx]: {
          correct: isCorrect,
          explanation: q.explanation || (isCorrect ? "Chính xác!" : "Sai rồi. Hãy xem lại đáp án đúng."),
        },
      }));
    }
  }, [questions, results]);

  // Handle text input for short_answer / fill_blank
  const handleTextInput = useCallback((questionIdx, value) => {
    setTextInputs((prev) => ({ ...prev, [questionIdx]: value }));
  }, []);

  // Submit text answer for evaluation via LLM (types 2 & 4)
  const handleSubmitTextAnswer = useCallback(async (questionIdx) => {
    const q = questions[questionIdx];
    const userAnswer = textInputs[questionIdx]?.trim();
    if (!userAnswer) return;

    // Resolve the correct answer from options
    const correctOption = q.options?.find((o) => o.isCorrect === true || o.is_correct === true);
    const actualAnswer = correctOption?.optionText || correctOption?.option_text || correctOption?.text || "";

    setEvaluating((prev) => ({ ...prev, [questionIdx]: true }));
    setAnswers((prev) => ({ ...prev, [questionIdx]: userAnswer }));

    try {
      const result = await evaluateAnswer({
        question: q,
        actualAnswer,
        userAnswer,
      });
      setResults((prev) => ({
        ...prev,
        [questionIdx]: {
          correct: result.correct,
          explanation: result.explanation,
        },
      }));
    } catch {
      setResults((prev) => ({
        ...prev,
        [questionIdx]: {
          correct: false,
          explanation: "Không thể đánh giá câu trả lời. Vui lòng thử lại.",
        },
      }));
    } finally {
      setEvaluating((prev) => ({ ...prev, [questionIdx]: false }));
    }
  }, [questions, textInputs, evaluateAnswer]);

  const goNext = () => {
    if (currentIndex < totalQuestions - 1) setCurrentIndex(currentIndex + 1);
  };
  const goPrev = () => {
    if (currentIndex > 0) setCurrentIndex(currentIndex - 1);
  };

  // Calculate score
  const getScore = () => {
    let correct = 0;
    let answered = 0;
    Object.keys(results).forEach((idx) => {
      answered++;
      if (results[idx]?.correct) correct++;
    });
    return { correct, answered, total: totalQuestions };
  };

  const handleFinishQuiz = () => {
    const score = getScore();
    setShowSummary(true);
    onFinish?.(score);
  };

  const getQuestionTypeLabel = (q) => {
    const qType = q.type || q.question_type;
    switch (qType) {
      case ETypeQuestion.MULTIPLE_CHOICE: return "Trắc nghiệm";
      case ETypeQuestion.FILL_IN_BLANK: return "Điền vào chỗ trống";
      case ETypeQuestion.TRUE_FALSE: return "Đúng / Sai";
      case ETypeQuestion.SHORT_ANSWER: return "Tự luận ngắn";
      default: return "Câu hỏi";
    }
  };

  // Types 2 (FILL_IN_BLANK) and 4 (SHORT_ANSWER) use a textbox
  const isTextType = (q) => {
    const qType = q.type || q.question_type;
    return qType === ETypeQuestion.FILL_IN_BLANK || qType === ETypeQuestion.SHORT_ANSWER;
  };

  // Summary screen
  if (showSummary) {
    const score = getScore();
    const percentage = totalQuestions > 0 ? Math.round((score.correct / totalQuestions) * 100) : 0;
    const targetScore = (targetGrade || 7) * 10;
    const passed = percentage >= targetScore;

    return (
      <div className="quiz-overlay">
        <div className="quiz-popup">
          <div className="quiz-popup-header">
            <h2>Kết quả kiểm tra</h2>
            <span className="quiz-subject-tag">{subjectName}</span>
          </div>

          <div className="quiz-summary">
            <div className={`quiz-score-circle ${passed ? "score-pass" : "score-fail"}`}>
              <span className="score-number">{percentage}%</span>
              <span className="score-label">{passed ? "Đạt" : "Không đạt"}</span>
            </div>
            <div className="quiz-score-details">
              <div className="score-detail-row">
                <span>Đúng</span>
                <span className="score-correct">{score.correct}/{totalQuestions}</span>
              </div>
              <div className="score-detail-row">
                <span>Sai</span>
                <span className="score-wrong">{score.answered - score.correct}/{totalQuestions}</span>
              </div>
              <div className="score-detail-row">
                <span>Chưa trả lời</span>
                <span>{totalQuestions - score.answered}/{totalQuestions}</span>
              </div>
              <div className="score-detail-row">
                <span>Mục tiêu</span>
                <span className="score-target">{targetScore}%</span>
              </div>
            </div>
          </div>

          {!passed && (
            <div className="quiz-regenerate-notice">
              <span>⚠️ Bạn chưa đạt mục tiêu ({targetScore}%). Lộ trình học đang được tạo lại...</span>
            </div>
          )}

          {/* Review questions */}
          <div className="quiz-review-list">
            {questions.map((q, idx) => {
              const r = results[idx];
              return (
                <div key={idx} className={`quiz-review-item ${r?.correct ? "review-correct" : r ? "review-wrong" : "review-unanswered"}`}>
                  <span className="review-num">Câu {idx + 1}</span>
                  <span className="review-type">{getQuestionTypeLabel(q)}</span>
                  <span className="review-status">
                    {r?.correct ? "Đúng" : r ? "Sai" : "Bỏ qua"}
                  </span>
                </div>
              );
            })}
          </div>

          <div className="quiz-popup-actions">
            <button className="quiz-btn quiz-btn-primary" onClick={onClose}>
              Đóng
            </button>
          </div>
        </div>
      </div>
    );
  }

  const q = currentQuestion;
  const qType = q?.type || q?.question_type;
  const questionText = q?.text || q?.question || "";
  const result = results[currentIndex];

  return (
    <div className="quiz-overlay">
      <div className="quiz-popup">
        {/* Header */}
        <div className="quiz-popup-header">
          <div className="quiz-header-left">
            <h2>Kiểm tra - {subjectName}</h2>
            <span className="quiz-progress-text">
              Câu {currentIndex + 1} / {totalQuestions}
            </span>
          </div>
          <button className="quiz-close-btn" onClick={onClose}>X</button>
        </div>

        {/* Progress bar */}
        <div className="quiz-progress-bar">
          <div
            className="quiz-progress-fill"
            style={{ width: `${((currentIndex + 1) / totalQuestions) * 100}%` }}
          />
        </div>

        {/* Question navigation dots */}
        <div className="quiz-nav-dots">
          {questions.map((_, idx) => (
            <button
              key={idx}
              className={`quiz-dot ${idx === currentIndex ? "dot-active" : ""} ${results[idx]?.correct ? "dot-correct" : results[idx] ? "dot-wrong" : answers[idx] !== undefined ? "dot-answered" : ""}`}
              onClick={() => setCurrentIndex(idx)}
            >
              {idx + 1}
            </button>
          ))}
        </div>

        {/* Question content */}
        <div className="quiz-question-area">
          <div className="quiz-question-meta">
            <span className={`quiz-type-badge badge-${qType}`}>
              {getQuestionTypeLabel(q)}
            </span>
          </div>
          <p className="quiz-question-text">{questionText}</p>

          {/* Options for multiple_choice / true_false */}
          {!isTextType(q) && q.options && (
            <div className="quiz-options">
              {q.options.map((opt, oidx) => {
                const selected = answers[currentIndex] === oidx;
                const isCorrect = opt.isCorrect === true || opt.is_correct === true;
                const showResult = result !== undefined;

                let optClass = "quiz-option";
                if (selected) optClass += " option-selected";
                if (showResult && isCorrect) optClass += " option-correct";
                if (showResult && selected && !isCorrect) optClass += " option-wrong";

                return (
                  <button
                    key={oidx}
                    className={optClass}
                    onClick={() => handleOptionSelect(currentIndex, oidx)}
                    disabled={result !== undefined}
                  >
                    <span className="option-marker">
                      {String.fromCharCode(65 + oidx)}
                    </span>
                    <span className="option-text">
                      {opt.optionText || opt.option_text || opt.text || opt}
                    </span>
                  </button>
                );
              })}
            </div>
          )}

          {/* Text input for short_answer / fill_blank */}
          {isTextType(q) && (
            <div className="quiz-text-input-area">
              <textarea
                className="quiz-text-input"
                value={textInputs[currentIndex] || ""}
                onChange={(e) => handleTextInput(currentIndex, e.target.value)}
                placeholder={
                  qType === ETypeQuestion.FILL_IN_BLANK
                    ? "Điền vào chỗ trống..."
                    : "Nhập câu trả lời..."
                }
                disabled={result !== undefined}
                rows={3}
              />
              {result === undefined && (
                <button
                  className="quiz-btn quiz-btn-submit"
                  onClick={() => handleSubmitTextAnswer(currentIndex)}
                  disabled={!textInputs[currentIndex]?.trim() || evaluating[currentIndex]}
                >
                  {evaluating[currentIndex] ? "Đang đánh giá..." : "Gửi câu trả lời"}
                </button>
              )}
            </div>
          )}

          {/* Result feedback */}
          {result && (
            <div className={`quiz-feedback ${result.correct ? "feedback-correct" : "feedback-wrong"}`}>
              <div className="feedback-header">
                {result.correct ? "Chính xác!" : "Chưa chính xác"}
              </div>
              <p className="feedback-explanation">{result.explanation}</p>
            </div>
          )}
        </div>

        {/* Navigation */}
        <div className="quiz-popup-actions">
          <button
            className="quiz-btn quiz-btn-secondary"
            onClick={goPrev}
            disabled={currentIndex === 0}
          >
            Trước
          </button>

          <div className="quiz-action-center">
            {Object.keys(results).length === totalQuestions && (
              <button className="quiz-btn quiz-btn-finish" onClick={handleFinishQuiz}>
                Nộp bài
              </button>
            )}
          </div>

          {currentIndex < totalQuestions - 1 ? (
            <button className="quiz-btn quiz-btn-secondary" onClick={goNext}>
              Tiếp
            </button>
          ) : (
            <button className="quiz-btn quiz-btn-finish" onClick={handleFinishQuiz}>
              Nộp bài
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default QuizPopup;
