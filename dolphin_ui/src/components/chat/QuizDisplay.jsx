import {
  Box,
  Button,
  FormControlLabel,
  Paper,
  Radio,
  RadioGroup,
  Typography,
} from "@mui/material";
import axios from "axios";
import React, { useEffect, useState } from "react";

const APP_URL =process.env.REACT_APP_BASE_URL;

const QuizDisplay = ({ quizContet }) => {
  const [answers, setAnswers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null); 

  // initialize answers
  useEffect(() => {
    setAnswers(new Array(quizContet.quiz_items.length).fill(null));
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
    setAnswers(new Array(quizContet.quiz_items.length).fill(null));
    setResult(null);
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <Typography>{quizContet.content}</Typography>


      {/* ===== QUESTIONS ===== */}
      {quizContet.quiz_items.map((item, qIndex) => (
        <Paper
          key={qIndex}
          elevation={0}
          sx={{
            p: 3,
            borderRadius: 3,
            border: "1px solid #e5e7eb",
          }}
        >
          <Typography fontWeight={600} mb={1.5}>
            {qIndex + 1}. {item.question}
          </Typography>

          <RadioGroup
            value={answers[qIndex] ?? ""}
            onChange={(e) =>
              handleChange(qIndex, Number(e.target.value))
            }
          >
            {item.options.map((option, oIndex) => (
              <FormControlLabel
                key={oIndex}
                value={oIndex}
                control={<Radio />}
                label={option}
                sx={{
                  mb: 1,
                  border: "1px solid #e5e7eb",
                  borderRadius: 2,
                  px: 1,
                  transition: "all 0.2s ease",
                }}
              />
            ))}
          </RadioGroup>
        </Paper>
      ))}

      
      {/* ===== RESULT SUMMARY ===== */}
      {result && (
        <Paper
          elevation={0}
          sx={{
            p: 2,
            borderRadius: 2,
            border: "1px solid #e5e7eb",
            backgroundColor: "#f8fafc",
          }}
        >
          <Typography fontWeight={600}>
            You scored {result.score_percent}% ({result.correct_count}/
            {result.total})
          </Typography>

          <Typography mt={1} fontWeight={500}>
            Correct answers:
          </Typography>

          <Box component="ul" sx={{ pl: 2, mt: 1 }}>
            {result.corrections.map((item, idx) => {
              const isCorrect =
                item.correct_answer === item.user_answer;

              return (
                <li key={idx}>
                  <Typography
                    sx={{
                      color: isCorrect ? "green" : "red",
                      fontSize: "0.9rem",
                    }}
                  >
                    Q{idx + 1}: Correct: {item.correct_answer} | You chose:{" "}
                    {item.user_answer || "No answer"}
                  </Typography>
                </li>
              );
            })}
          </Box>
        </Paper>
      )}

      {/* ===== ACTION BUTTONS ===== */}
      <Box sx={{ display: "flex", gap: 1 }}>
        <Button
          variant="contained"
          onClick={submitQuiz}
          disabled={loading || result}
          sx={{ textTransform: "none" }}
        >
          {loading ? "Submitting..." : "Submit Quiz"}
        </Button>

        <Button
          variant="outlined"
          onClick={retakeQuiz}
          disabled={loading}
          sx={{ textTransform: "none" }}
        >
          Retake Quiz
        </Button>
      </Box>
    </Box>
  );
};

export default QuizDisplay;
