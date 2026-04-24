import { useState, useRef, useEffect, useCallback } from "react";
import "./chatbot.css";
import {
  Send,
  BookOpen,
  Bot,
  User,
  Copy,
  FileText,
  Play,
  Square,
  Clock,
  CheckCircle2,
  Loader2,
  CalendarDays,
  ChevronDown,
  ChevronUp,
  Trophy,
  XCircle,
  Circle,
} from "lucide-react";
import { usePlannerService } from "../../service/planner/usePlannerService";
import { useChatbotService } from "../../service/chatbot/useChatbotService";
import QuizPopup from "../quiz-popup/quiz-popup";
import toast from "react-hot-toast";

// Session states
const SESSION_STATE = {
  IDLE: "idle",
  STUDYING: "studying",
  GENERATING_QUIZ: "generating_quiz",
  QUIZ: "quiz",
};

const Chatbot = ({ user }) => {
  // Chat state
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const messagesEndRef = useRef(null);

  // Subject & planner state
  const [subjects, setSubjects] = useState([]);
  const [selectedSubjectId, setSelectedSubjectId] = useState(null);
  const [loadingSubjects, setLoadingSubjects] = useState(true);

  // Study session state
  const [sessionState, setSessionState] = useState(SESSION_STATE.IDLE);
  const [sessionStartTime, setSessionStartTime] = useState(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const timerRef = useRef(null);

  // Study plan sessions from DB
  const [planSessions, setPlanSessions] = useState([]);
  const [selectedPlanSession, setSelectedPlanSession] = useState(null);
  const [showSessions, setShowSessions] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [expandedSessionId, setExpandedSessionId] = useState(null);

  // Quiz state
  const [quizQuestions, setQuizQuestions] = useState([]);

  const { getSubjects, getStudyPlan } = usePlannerService();
  const { streamChat, evaluateAnswer, updateSessionLearningStatus, generatePlan } = useChatbotService();

  // Load subjects on mount
  useEffect(() => {
    if (!user) return;
    (async () => {
      try {
        setLoadingSubjects(true);
        const subs = await getSubjects();
        setSubjects(subs);
        if (subs.length > 0 && !selectedSubjectId) {
          setSelectedSubjectId(subs[0].id);
        }
      } catch (err) {
        console.error("Failed to load subjects:", err);
      } finally {
        setLoadingSubjects(false);
      }
    })();
  }, [user, getSubjects, selectedSubjectId]);

  // Load plan sessions when subject changes
  useEffect(() => {
    if (!selectedSubjectId) {
      setPlanSessions([]);
      setSelectedPlanSession(null);
      setShowSessions(false);
      return;
    }
    const subject = subjects.find((s) => s.id === selectedSubjectId);
    if (!subject || subject.plan_status !== "completed") {
      setPlanSessions([]);
      setSelectedPlanSession(null);
      setShowSessions(false);
      return;
    }
    (async () => {
      try {
        setLoadingSessions(true);
        const plan = await getStudyPlan(selectedSubjectId);
        if (plan?.sessions) {
          setPlanSessions(plan.sessions);
          // Auto-select first not_started session
          const nextSession = plan.sessions.find(
            (s) => s.learning_status === "not_started" || s.status === "scheduled"
          );
          setSelectedPlanSession(nextSession || null);
          setShowSessions(true);
        } else {
          setPlanSessions([]);
          setSelectedPlanSession(null);
        }
      } catch {
        setPlanSessions([]);
        setSelectedPlanSession(null);
      } finally {
        setLoadingSessions(false);
      }
    })();
  }, [selectedSubjectId, subjects, getStudyPlan]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Timer
  useEffect(() => {
    if (sessionState === SESSION_STATE.STUDYING && sessionStartTime) {
      timerRef.current = setInterval(() => {
        setElapsedSeconds(Math.floor((Date.now() - sessionStartTime) / 1000));
      }, 1000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [sessionState, sessionStartTime]);

  const formatTime = (totalSeconds) => {
    const h = Math.floor(totalSeconds / 3600);
    const m = Math.floor((totalSeconds % 3600) / 60);
    const s = totalSeconds % 60;
    if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  };
  const selectedSubject = subjects.find((s) => s.id === selectedSubjectId);

  // Start study session
  const handleStartSession = () => {
    if (!selectedSubjectId) {
      toast.error("Vui lòng chọn môn học trước khi bắt đầu.");
      return;
    }
    setSessionState(SESSION_STATE.STUDYING);
    setSessionStartTime(Date.now());
    setElapsedSeconds(0);

    const sessionInfo = selectedPlanSession
      ? `\n\n📖 **Buổi học hôm nay:** ${selectedPlanSession.title || "Buổi học"}\n⏰ ${selectedPlanSession.start_time} - ${selectedPlanSession.end_time}\n${selectedPlanSession.content ? `📝 ${selectedPlanSession.content.substring(0, 200)}...` : ""}`
      : "";

    setMessages([
      {
        id: 1,
        role: "assistant",
        content: `Bắt đầu phiên học môn **${selectedSubject?.name || ""}**.${sessionInfo}\n\nBạn có thể hỏi bất kỳ câu hỏi nào về môn học. Khi muốn kết thúc, nhấn nút "Kết thúc & Kiểm tra".`,
        timestamp: new Date(),
      },
    ]);
  };

  // End session -> generate quiz via chatbot streaming (MCP tool call)
  const handleEndSession = useCallback(async () => {
    if (timerRef.current) clearInterval(timerRef.current);
    setSessionState(SESSION_STATE.GENERATING_QUIZ);

    const sessionTitle = selectedPlanSession?.title || selectedSubject?.name || "Môn học";
    const sessionContent = selectedPlanSession?.content || "";
    const quizDescription = sessionContent ? ` với nội dung buổi học: "${sessionContent.substring(0, 500)}"` : "";

    const quizPrompt = `Hãy tạo bài kiểm tra gồm 10 câu hỏi về buổi học "${sessionTitle}"${quizDescription} để đánh giá kiến thức của tôi. Sử dụng tool generate_quiz với title là "${sessionTitle}", description là "${sessionContent.substring(0, 1000)}" và totalQuestions là 10.`;
    console.log("Quiz prompt:", quizPrompt);

    setMessages((prev) => [
      ...prev,
      { id: Date.now(), role: "system", content: "Đang tạo bài kiểm tra...", timestamp: new Date() },
    ]);

    let collectedQuiz = [];

    try {
      await streamChat({
        question: quizPrompt,
        userId: user.id,
        subjectId: selectedSubjectId,
        lectureTitle: sessionTitle,
        lectureContent: sessionContent,
        onToken: () => {},
        onToolResult: (toolResult) => {
          if (toolResult.tool_name === "generate_quiz" && toolResult.success) {
            try {
              let parsed = toolResult.result;
              if (typeof parsed === "string") parsed = JSON.parse(parsed);
              if (parsed?.tool_result && Array.isArray(parsed.tool_result)) {
                collectedQuiz = parsed.tool_result;
              } else if (Array.isArray(parsed)) {
                collectedQuiz = parsed;
              }
              // Open quiz immediately as soon as tool result arrives
              if (collectedQuiz.length > 0) {
                setQuizQuestions(collectedQuiz);
                setSessionState(SESSION_STATE.QUIZ);
              }
            } catch {
              console.error("Failed to parse quiz result");
            }
          }
        },
        onThinking: () => {},
        onError: (err) => {
          toast.error("Lỗi khi tạo bài kiểm tra: " + err);
          setSessionState(SESSION_STATE.STUDYING);
        },
        onDone: () => {
          if (collectedQuiz.length === 0) {
            toast.error("Không thể tạo bài kiểm tra. Vui lòng thử lại.");
            setSessionState(SESSION_STATE.STUDYING);
            setSessionStartTime(Date.now() - elapsedSeconds * 1000);
          }
        },
      });
    } catch (err) {
      toast.error("Lỗi kết nối: " + err.message);
      setSessionState(SESSION_STATE.STUDYING);
      setSessionStartTime(Date.now() - elapsedSeconds * 1000);
    }
  }, [selectedSubject, selectedSubjectId, selectedPlanSession, user, streamChat, elapsedSeconds]);

  // Quiz finished -> update learning_status & generate new plan if failed
  const handleQuizFinish = useCallback(async (score) => {
    const percentage = score.total > 0 ? Math.round((score.correct / score.total) * 100) : 0;
    const targetScore = (selectedSubject?.target_grade || 7) * 10; // target_grade is on 10-point scale
    const passed = percentage >= targetScore;

    try {
      // Use the selected plan session if available, otherwise fall back to finding one
      let currentSession = selectedPlanSession;
      if (!currentSession) {
        const plan = await getStudyPlan(selectedSubjectId);
        if (plan?.sessions?.length > 0) {
          currentSession = plan.sessions.find(
            (s) => s.status === "scheduled" || s.learning_status === "not_started"
          );
        }
      }

      if (currentSession) {
        await updateSessionLearningStatus(currentSession.id, passed ? "passed" : "failed", percentage);
        if (!passed) {
          await generatePlan(selectedSubjectId);
          toast(`Bạn đạt ${percentage}% (mục tiêu: ${targetScore}%). Lộ trình học đã được tạo lại.`, { duration: 4000 });
        } else {
          toast.success(`Xuất sắc! Bạn đạt ${percentage}% (mục tiêu: ${targetScore}%). Phiên học hoàn thành.`);
        }
      }
    } catch (err) {
      console.error("Failed to update session status:", err);
    }
  }, [selectedSubjectId, selectedSubject, selectedPlanSession, getStudyPlan, updateSessionLearningStatus, generatePlan]);

  const handleQuizClose = () => {
    setSessionState(SESSION_STATE.IDLE);
    setQuizQuestions([]);
    setMessages([]);
  };

  // Send chat message
  const handleSend = async () => {
    if (!inputValue.trim() || isLoading) return;
    if (sessionState !== SESSION_STATE.STUDYING) return;

    const userMsg = { id: Date.now(), role: "user", content: inputValue, timestamp: new Date() };
    setMessages((prev) => [...prev, userMsg]);
    const question = inputValue;
    setInputValue("");
    setIsLoading(true);
    setIsThinking(true);

    const assistantMsgId = Date.now() + 1;
    setMessages((prev) => [
      ...prev,
      { id: assistantMsgId, role: "assistant", content: "", timestamp: new Date(), streaming: true },
    ]);

    try {
      await streamChat({
        question,
        userId: user.id,
        subjectId: selectedSubjectId,
        lectureTitle: selectedPlanSession?.title || "",
        lectureContent: selectedPlanSession?.content || "",
        onToken: (token) => {
          setIsThinking(false);
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantMsgId ? { ...m, content: m.content + token } : m))
          );
        },
        onToolResult: () => {},
        onThinking: () => setIsThinking(true),
        onError: (err) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantMsgId ? { ...m, content: "Lỗi: " + err, streaming: false } : m))
          );
        },
        onDone: () => {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantMsgId ? { ...m, streaming: false } : m))
          );
        },
      });
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantMsgId ? { ...m, content: "Lỗi kết nối: " + err.message, streaming: false } : m))
      );
    } finally {
      setIsLoading(false);
      setIsThinking(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleCopy = (content) => {
    navigator.clipboard.writeText(content);
    toast.success("Đã sao chép!");
  };

  const renderMessageContent = (content) => {
    if (!content) return null;
    const html = content
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\n/g, "<br/>")
      .replace(/• /g, "&bull; ")
      .replace(/- /g, "&ndash; ");
    return <div className="message-text" dangerouslySetInnerHTML={{ __html: html }} />;
  };

  return (
    <div className="chatbot">
      {/* Sidebar */}
      <div className="chat-sidebar">
        <div className="chat-sidebar-header">
          <BookOpen size={18} />
          <span>Môn học</span>
        </div>

        {loadingSubjects ? (
          <div className="sidebar-loading">
            <Loader2 size={18} className="spin-icon" />
            <span>Đang tải...</span>
          </div>
        ) : subjects.length === 0 ? (
          <div className="sidebar-empty">Chưa có môn học nào.</div>
        ) : (
          <div className="subject-list">
            {subjects.map((subject) => (
              <button
                key={subject.id}
                className={`subject-btn ${selectedSubjectId === subject.id ? "subject-btn-active" : ""}`}
                onClick={() => {
                  if (sessionState === SESSION_STATE.IDLE) setSelectedSubjectId(subject.id);
                }}
                disabled={sessionState !== SESSION_STATE.IDLE}
              >
                <span>{subject.emoji}</span>
                <span>{subject.name}</span>
                {subject.plan_status === "completed" && (
                  <CheckCircle2 size={14} className="subject-status-icon status-ok" />
                )}
              </button>
            ))}
          </div>
        )}

        {/* Study Plan Sessions */}
        {selectedSubjectId && sessionState === SESSION_STATE.IDLE && (
          <div className="session-list-section">
            <button
              className="session-list-toggle"
              onClick={() => setShowSessions((v) => !v)}
            >
              <CalendarDays size={16} />
              <span>Buổi học ({planSessions.length})</span>
              {showSessions ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>

            {showSessions && (
              <div className="session-list">
                {loadingSessions ? (
                  <div className="sidebar-loading">
                    <Loader2 size={14} className="spin-icon" />
                    <span>Đang tải...</span>
                  </div>
                ) : planSessions.length === 0 ? (
                  <div className="sidebar-empty">Chưa có buổi học nào.</div>
                ) : (
                  planSessions.map((ps) => {
                    const isSelected = selectedPlanSession?.id === ps.id;
                    const isPassed = ps.learning_status === "passed";
                    const isFailed = ps.learning_status === "failed";
                    const isNotStarted = ps.learning_status === "not_started";
                    const isExpanded = expandedSessionId === ps.id;

                    return (
                      <div key={ps.id} className={`plan-session-card ${isSelected && !isPassed ? "plan-session-selected" : ""} ${isPassed ? "plan-session-passed" : ""} ${isFailed ? "plan-session-failed" : ""} ${isNotStarted ? "plan-session-not-started" : ""}`}>
                        <button
                          className="plan-session-btn"
                          onClick={() => {
                            if (!isPassed) {
                              setSelectedPlanSession(ps);
                            }
                            setExpandedSessionId(isExpanded ? null : ps.id);
                          }}
                        >
                          <div className="plan-session-status-icon">
                            {isPassed && <CheckCircle2 size={14} />}
                            {isFailed && <XCircle size={14} />}
                            {isNotStarted && <Circle size={14} />}
                          </div>
                          <div className="plan-session-info">
                            <span className="plan-session-title">{ps.title || "Buổi học"}</span>
                            <span className="plan-session-meta">
                              {ps.session_date && new Date(ps.session_date).toLocaleDateString("vi-VN", { weekday: "short", day: "2-digit", month: "2-digit" })}
                              {" · "}
                              {ps.start_time} - {ps.end_time}
                            </span>
                          </div>
                          <div className="plan-session-right">
                            {isPassed && ps.score != null && (
                              <span className="plan-session-score plan-session-score-pass">
                                <Trophy size={10} /> {ps.score}%
                              </span>
                            )}
                            {isFailed && ps.score != null && (
                              <span className="plan-session-score plan-session-score-fail">
                                {ps.score}%
                              </span>
                            )}
                            {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                          </div>
                        </button>

                        {isExpanded && (
                          <div className="plan-session-detail">
                            {ps.content ? (
                              <p className="plan-session-content">{ps.content}</p>
                            ) : (
                              <p className="plan-session-content plan-session-no-content">Chưa có nội dung chi tiết.</p>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </div>
        )}

        {/* Session timer */}
        {sessionState !== SESSION_STATE.IDLE && (
          <div className="session-info-panel">
            <div className="session-timer">
              <Clock size={16} />
              <span className="timer-display">{formatTime(elapsedSeconds)}</span>
            </div>
            <span className="session-subject-label">
              {selectedSubject?.emoji} {selectedSubject?.name}
            </span>
          </div>
        )}

        {/* Action buttons */}
        <div className="sidebar-actions">
          {sessionState === SESSION_STATE.IDLE && (
            <button className="session-btn session-btn-start" onClick={handleStartSession} disabled={!selectedSubjectId}>
              <Play size={16} /> Bắt đầu học
            </button>
          )}
          {sessionState === SESSION_STATE.STUDYING && (
            <button className="session-btn session-btn-end" onClick={handleEndSession}>
              <Square size={16} /> Kết thúc & Kiểm tra
            </button>
          )}
          {sessionState === SESSION_STATE.GENERATING_QUIZ && (
            <button className="session-btn session-btn-loading" disabled>
              <Loader2 size={16} className="spin-icon" /> Đang tạo đề thi...
            </button>
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="chat-main">
        {/* Idle welcome */}
        {sessionState === SESSION_STATE.IDLE && messages.length === 0 && (
          <div className="chat-welcome">
            <div className="welcome-content">
              <Bot size={48} className="welcome-icon" />
              <h2>Trợ lý học tập AI</h2>
              <p>Chọn môn học và nhấn "Bắt đầu học" để mở phiên học mới.</p>
              <p>Trong phiên học, bạn có thể hỏi đáp với chatbot và khi kết thúc sẽ có bài kiểm tra đánh giá.</p>
              <div className="welcome-features">
                <div className="feature-item">
                  <FileText size={20} />
                  <span>Hỏi đáp theo tài liệu môn học</span>
                </div>
                <div className="feature-item">
                  <Clock size={20} />
                  <span>Tính giờ học tập</span>
                </div>
                <div className="feature-item">
                  <CheckCircle2 size={20} />
                  <span>Kiểm tra & đánh giá tự động</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Chat messages */}
        {(sessionState !== SESSION_STATE.IDLE || messages.length > 0) && (
          <>
            <div className="chat-messages">
              {messages.map((msg) => {
                // if (msg.role === "tool") {
                //   return (
                //     <div key={msg.id} className="chat-message chat-message-tool">
                //       <div className="tool-result-badge">
                //         <FileText size={14} />
                //         <span>Tool: {msg.toolName}</span>
                //       </div>
                //     </div>
                //   );
                // }
                if (msg.role === "system") {
                  return (
                    <div key={msg.id} className="chat-message chat-message-system">
                      <div className="system-message">
                        <Loader2 size={14} className="spin-icon" />
                        <span>{msg.content}</span>
                      </div>
                    </div>
                  );
                }
                return (
                  <div key={msg.id} className={`chat-message chat-message-${msg.role}`}>
                    <div className="message-avatar">
                      {msg.role === "assistant" ? <Bot size={20} /> : <User size={20} />}
                    </div>
                    <div className="message-content">
                      <div className="message-bubble">
                        {msg.streaming && !msg.content ? (
                          <div className="typing-indicator">
                            <span></span><span></span><span></span>
                          </div>
                        ) : (
                          renderMessageContent(msg.content)
                        )}
                      </div>
                      {msg.role === "assistant" && msg.content && (
                        <div className="message-actions">
                          <button className="msg-action-btn" title="Copy" onClick={() => handleCopy(msg.content)}>
                            <Copy size={14} />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {isThinking && !messages.some((m) => m.streaming && !m.content) && (
                <div className="chat-message chat-message-assistant">
                  <div className="message-avatar"><Bot size={20} /></div>
                  <div className="message-content">
                    <div className="message-bubble">
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            {sessionState === SESSION_STATE.STUDYING && (
              <div className="chat-input-area">
                <div className="chat-input-wrapper">
                  <textarea
                    className="chat-input"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={handleKeyPress}
                    placeholder="Hỏi bất cứ điều gì về bài học..."
                    rows={1}
                  />
                  <button className="send-btn" onClick={handleSend} disabled={!inputValue.trim() || isLoading}>
                    <Send size={18} />
                  </button>
                </div>
                <p className="chat-disclaimer">AI có thể sai sót. Luôn kiểm tra thông tin quan trọng với tài liệu gốc.</p>
              </div>
            )}
          </>
        )}
      </div>

      {/* Quiz Popup */}
      {sessionState === SESSION_STATE.QUIZ && quizQuestions.length > 0 && (
        <QuizPopup
          questions={quizQuestions}
          subjectName={selectedSubject?.name || "Môn học"}
          targetGrade={selectedSubject?.target_grade || 7}
          onClose={handleQuizClose}
          onFinish={handleQuizFinish}
          evaluateAnswer={evaluateAnswer}
        />
      )}
    </div>
  );
};

export default Chatbot;
