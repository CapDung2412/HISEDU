import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Quiz } from "@/components/Quiz";
import type { QuizData, QuizSubmitResponse } from "@/lib/types";

const quiz: QuizData = {
  quiz_id: "quiz-1",
  questions: Array.from({ length: 5 }, (_, index) => ({
    id: `q${index + 1}`,
    prompt: `Câu hỏi số ${index + 1}?`,
    options: ["a", "b", "c", "d"].map((id) => ({ id, text: `Lựa chọn ${id.toUpperCase()}` }))
  }))
};

const marked: QuizSubmitResponse = {
  quiz_id: "quiz-1",
  score: 5,
  max_score: 5,
  results: quiz.questions.map((question) => ({
    question_id: question.id,
    selected_option_id: "a",
    correct: true,
    correct_option_id: "a",
    explanation: "Đây là đáp án phù hợp với nội dung vừa học.",
    source_ids: ["S1"]
  }))
};

describe("Quiz", () => {
  it("không lộ đáp án, chấm đủ 5 câu và cho phép làm lại", async () => {
    const user = userEvent.setup();
    const submit = vi.fn().mockResolvedValue(marked);
    render(<Quiz quiz={quiz} onSubmit={submit} />);

    expect(screen.queryByText("Đây là đáp án phù hợp với nội dung vừa học.")).not.toBeInTheDocument();

    const options = screen.getAllByRole("radio");
    for (let questionIndex = 0; questionIndex < 5; questionIndex += 1) {
      await user.click(options[questionIndex * 4]);
    }
    await user.click(screen.getByRole("button", { name: "Nộp bài" }));

    await waitFor(() => expect(submit).toHaveBeenCalledWith("quiz-1", {
      q1: "a", q2: "a", q3: "a", q4: "a", q5: "a"
    }));
    expect(await screen.findByText("5", { selector: "p" })).toBeInTheDocument();
    expect(screen.getAllByText("Đây là đáp án phù hợp với nội dung vừa học.")).toHaveLength(5);

    await user.click(screen.getByRole("button", { name: "Làm lại quiz" }));
    expect(screen.getByText("Đã trả lời 0/5 câu")).toBeInTheDocument();
  });

  it("nhắc khi học sinh chưa trả lời đủ câu", async () => {
    const user = userEvent.setup();
    const submit = vi.fn();
    render(<Quiz quiz={quiz} onSubmit={submit} />);

    await user.click(screen.getByRole("button", { name: "Nộp bài" }));
    expect(screen.getByRole("alert")).toHaveTextContent("còn 5 câu chưa chọn");
    expect(submit).not.toHaveBeenCalled();
  });
});

