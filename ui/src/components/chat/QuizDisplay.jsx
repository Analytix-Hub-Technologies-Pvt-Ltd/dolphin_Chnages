import React, { useEffect, useState } from "react";
import axios from "axios";
import APP_URL from "../../config/apiConfig";

const QuizDisplay = ({ quizContet }) => {
  const [answers, setAnswers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  // initialize answers
  useEffect(() => {
    setAnswers(new Array(quizContet?.quiz_items?.length || 0).fill(null));
  }, [quizContet]);

  const handleChange = (qIndex, optionIndex) => {
    if (result) return; // lock answers after submit
    setAnswers((prev) => {
      const updated = [...prev];
      updated[qIndex] = optionIndex;
      return updated;
    });
  };

  const submitQuiz = async () => {
    setLoading(true);
    setResult(null);

    try {
      const resp = await axios.post(
        `${APP_URL}/quiz/grade`,
        {
          quiz_items: quizContet.quiz_items,
          user_answers: answers,
        },
        { headers: { "Content-Type": "application/json" } }
      );

      setResult(resp.data);
    } catch (err) {
      console.error(err.response?.data?.message || err.message);
    } finally {
      setLoading(false);
    }
  };

  const retakeQuiz = () => {
    setAnswers(new Array(quizContet?.quiz_items?.length || 0).fill(null));
    setResult(null);
  };

  return (
    <div className="flex flex-col gap-4 text-text-primary text-sm">
      <p className="m-0 leading-relaxed font-medium">{quizContet.content}</p>

      {/* ===== QUESTIONS ===== */}
      {quizContet?.quiz_items?.map((item, qIndex) => (
        <div
          key={qIndex}
          className="p-5 rounded-2xl bg-bg-paper border border-border-theme shadow-xs space-y-3"
        >
          <h4 className="font-semibold text-base text-text-primary m-0">
            {qIndex + 1}. {item.question}
          </h4>

          <div className="space-y-2">
            {item.options.map((option, oIndex) => {
              const isSelected = answers[qIndex] === oIndex;
              return (
                <label
                  key={oIndex}
                  className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer select-none transition-all ${
                    isSelected
                      ? "border-primary bg-primary/5 text-primary font-medium"
                      : "border-border-theme hover:bg-bg-default text-text-primary"
                  }`}
                >
                  <input
                    type="radio"
                    name={`quiz-q-${qIndex}`}
                    value={oIndex}
                    checked={isSelected}
                    disabled={Boolean(result)}
                    onChange={() => handleChange(qIndex, oIndex)}
                    className="w-4 h-4 text-primary accent-primary cursor-pointer"
                  />
                  <span className="text-sm">{option}</span>
                </label>
              );
            })}
          </div>
        </div>
      ))}

      {/* ===== RESULT SUMMARY ===== */}
      {result && (
        <div className="p-4 rounded-2xl bg-bg-paper border border-border-theme shadow-xs space-y-2">
          <p className="font-bold text-base text-text-primary m-0">
            You scored {result.score_percent}% ({result.correct_count}/
            {result.total})
          </p>

          <p className="font-semibold text-sm text-text-secondary m-0 mt-2">
            Correct answers:
          </p>

          <ul className="pl-5 space-y-1 mt-1 text-sm list-disc">
            {result.corrections.map((item, idx) => {
              const isCorrect = item.correct_answer === item.user_answer;
              return (
                <li key={idx} className={isCorrect ? "text-emerald-600" : "text-rose-600"}>
                  <span className="font-medium">
                    Q{idx + 1}: Correct: {item.correct_answer} | You chose:{" "}
                    {item.user_answer || "No answer"}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {/* ===== ACTION BUTTONS ===== */}
      <div className="flex items-center gap-3 pt-2">
        <button
          type="button"
          onClick={submitQuiz}
          disabled={loading || Boolean(result)}
          className="px-5 py-2 rounded-xl bg-primary text-white font-semibold text-sm shadow hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "Submitting..." : "Submit Quiz"}
        </button>

        <button
          type="button"
          onClick={retakeQuiz}
          disabled={loading}
          className="px-5 py-2 rounded-xl border border-border-theme text-text-primary font-semibold text-sm hover:bg-bg-default disabled:opacity-50 transition-colors"
        >
          Retake Quiz
        </button>
      </div>
    </div>
  );
};

export default QuizDisplay;
