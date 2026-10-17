import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Quiz } from "@/components/Quiz";
import type { QuizAnswerResponse, QuizData } from "@/lib/types";

const difficulties = ["remember", "remember", "understand", "understand", "apply"] as const;
const quiz: QuizData = {
  quiz_id: "quiz-1",
  questions: Array.from({ length: 5 }, (_, index) => ({
    id: `q${index + 1}`,
    prompt: `Câu hỏi số ${index + 1}?`,
    difficulty: difficulties[index],
    options: ["a", "b", "c", "d"].map((id) => ({ id, text: `Lựa chọn ${id.toUpperCase()}` }))
  }))
};

function responseFor(index: number): QuizAnswerResponse {
  const question = quiz.questions[index];
  return {
    quiz_id: quiz.quiz_id,
    result: {
      question_id: question.id,
      selected_option_id: "a",
      correct: true,
      correct_option_id: "a",
      explanation: `Giải thích câu ${index + 1}.`,
      source_ids: ["S1"]
    },
    next_question: quiz.questions[index + 1] ?? null,
    answered_count: index + 1,
    total_questions: 5,
    score_so_far: index + 1,
    completed: index === 4,
    adaptive_message: index === 4
      ? "Em đã hoàn thành 5 câu."
      : "Chính xác! Câu tiếp theo sẽ nâng độ khó thêm một mức."
  };
}

describe("Quiz", () => {
  it("chấm từng câu, điều chỉnh câu kế tiếp và cho phép làm lại", async () => {
    const user = userEvent.setup();
    const answer = vi.fn(async (_quizId: string, questionId: string) => {
      const index = quiz.questions.findIndex((item) => item.id === questionId);
      return responseFor(index);
    });
    const reset = vi.fn().mockResolvedValue(quiz);
    render(<Quiz quiz={quiz} onAnswer={answer} onReset={reset} />);

    expect(screen.getAllByRole("radio")).toHaveLength(4);
    expect(screen.queryByText("Giải thích câu 1.")).not.toBeInTheDocument();

    for (let index = 0; index < 5; index += 1) {
      await user.click(screen.getAllByRole("radio")[0]);
      await user.click(screen.getByRole("button", { name: "Kiểm tra đáp án" }));
      expect(await screen.findByText(`Giải thích câu ${index + 1}.`)).toBeInTheDocument();
      if (index < 4) {
        expect(screen.getByText(/Câu tiếp theo sẽ nâng độ khó/)).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: /Câu tiếp theo/ }));
      }
    }

    await waitFor(() => expect(answer).toHaveBeenCalledTimes(5));
    expect(screen.getByText("5", { selector: "p" })).toBeInTheDocument();
    expect(screen.getByText("Đã hoàn thành 5/5 câu · đúng 5 câu")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Làm lại quiz" }));
    await waitFor(() => expect(reset).toHaveBeenCalledWith("quiz-1"));
    expect(screen.getByText("Đã hoàn thành 0/5 câu · đúng 0 câu")).toBeInTheDocument();
  });

  it("không cho kiểm tra khi chưa chọn đáp án", () => {
    render(
      <Quiz
        quiz={quiz}
        onAnswer={vi.fn()}
        onReset={vi.fn()}
      />
    );

    expect(screen.getByRole("button", { name: "Kiểm tra đáp án" })).toBeDisabled();
    expect(screen.getByText("Nhận biết")).toBeInTheDocument();
  });
});
