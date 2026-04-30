import { useCallback, useMemo } from "react";
import useFetch from "../auth/useFetch";

const AI_SERVICE_URL = process.env.REACT_APP_AI_SERVICE_URL || "";
const PLANNER_API_URL = process.env.REACT_APP_PLANNER_API_URL || "http://localhost:8006";

const aiUrl = (path) => `${AI_SERVICE_URL}${path}`;
const plannerUrl = (path) => `${PLANNER_API_URL}${path}`;

/**
 * Service hooks for chatbot streaming, quiz generation, and session management.
 */
export function useChatbotService() {
  const fetchWithAuth = useFetch();

  // Stream chat completions from ai-service (SSE)
  const streamChat = useCallback(async ({ question, userId, subjectId, lectureTitle, lectureContent, onToken, onToolResult, onThinking, onError, onDone }) => {
    // console.log("Starting chat stream with question:", question, "userId:", userId, "subjectId:", subjectId);
    const res = await fetchWithAuth(aiUrl("/v1/chat/completions/stream"), {
      method: "POST",
      body: JSON.stringify({
        question,
        user_id: userId,
        subject_id: subjectId,
        stream: true,
        lecture_title: lectureTitle || "",
        lecture_content: lectureContent || "",
      }),
    });

    if (!res.ok) {
      const errText = await res.text();
      onError?.(errText);
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        if (trimmed === "data: [DONE]") {
          onDone?.();
          return;
        }
        if (trimmed.startsWith("data: ")) {
          try {
            const payload = JSON.parse(trimmed.slice(6));
            if (payload.type === "token") {
              onToken?.(payload.content);
            } else if (payload.type === "tool_result") {
              onToolResult?.(payload);
            } else if (payload.type === "thinking") {
              onThinking?.(payload.content);
            } else if (payload.type === "error") {
              onError?.(payload.message);
            }
          } catch {
            // Ignore malformed SSE lines
          }
        }
      }
    }
    onDone?.();
  }, [fetchWithAuth]);

  // Update learning_status of a study session
  const updateSessionLearningStatus = useCallback(async (sessionId, learningStatus, score = null) => {
    const body = { learning_status: learningStatus };
    if (score !== null) body.score = score;

    const res = await fetchWithAuth(plannerUrl(`/planner/sessions/${sessionId}/learning-status`), {
      method: "PUT",
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error("Failed to update session status");
    return res.json();
  }, [fetchWithAuth]);

  // Regenerate plan for subjects with failed sessions
  const regeneratePlan = useCallback(async (subjectId) => {
    const res = await fetchWithAuth(plannerUrl(`/planner/subjects/${subjectId}/regenerate-plan`), {
      method: "POST",
      body: JSON.stringify({}),
    });
    if (!res.ok) throw new Error("Failed to regenerate plan");
    return res.json();
  }, [fetchWithAuth]);

  // Generate plan for a subject (called after failed quiz to create new plan)
  const generatePlan = useCallback(async (subjectId) => {
    const res = await fetchWithAuth(plannerUrl(`/planner/subjects/${subjectId}/generate-plan`), {
      method: "POST",
      body: JSON.stringify({}),
    });
    if (!res.ok) throw new Error("Failed to generate plan");
    return res.json();
  }, [fetchWithAuth]);

  // Evaluate short_answer / fill_blank answers via LLM
  // question: full question object, actualAnswer: correct answer, userAnswer: user's input
  const evaluateAnswer = useCallback(async ({ question, actualAnswer, userAnswer }) => {
    const params = new URLSearchParams({
      actual_answer: actualAnswer,
      user_question: userAnswer,
    });

    const res = await fetchWithAuth(
      aiUrl(`/assistant/explain-answer?${params.toString()}`),
      {
        method: "POST",
        body: JSON.stringify(question),
      }
    );

    if (!res.ok) {
      throw new Error("Failed to evaluate answer");
    }

    const data = await res.json();
    const reply = data.reply || "";

    // Try to parse a JSON result from the LLM reply first
    try {
      const jsonMatch = reply.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]);
        if (typeof parsed.correct === "boolean" || parsed.correct === "true" || parsed.correct === "false") {
          return {
            correct: parsed.correct === true || parsed.correct === "true",
            explanation: parsed.explanation || reply,
          };
        }
      }
    } catch {
      // Fall through to keyword detection
    }

    // Detect correctness from common Vietnamese/English keywords in the reply
    const match = reply.match(/\{[\s\S]*\}/);
    if (match) {
      const parsed = JSON.parse(match[0]);

      const isCorrect = parsed.is_correct === true || parsed.is_correct === "true";
      const explanation = parsed.explanation;
      return { correct: isCorrect, explanation: explanation || reply };
    }

    return { correct: false, explanation: reply || "Không thể phân tích phản hồi từ AI." };

  }, [fetchWithAuth]);

  return useMemo(() => ({
    streamChat,
    updateSessionLearningStatus,
    regeneratePlan,
    generatePlan,
    evaluateAnswer,
  }), [streamChat, updateSessionLearningStatus, regeneratePlan, generatePlan, evaluateAnswer]);
}
