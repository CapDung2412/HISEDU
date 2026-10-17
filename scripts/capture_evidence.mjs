import { spawn } from "node:child_process";
import { writeFile } from "node:fs/promises";
import path from "node:path";

const root = "D:\\HISEDU";
const outputDir = path.join(root, "reports", "dossier_evidence");
const edgePath = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const profilePath = path.join(root, ".tmp-edge-evidence-cdp");
const sampleImage = path.join(outputDir, "ocr_question_sample.png");
const debugPort = 9333;

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const answer = {
  summary:
    "Trước Cách mạng tư sản Pháp, ngân khố nhà nước gần cạn kiệt vì chiến tranh và chi tiêu cung đình, trong khi chế độ thuế khóa bất công dồn gánh nặng lên Đẳng cấp thứ ba [S1].",
  sections: [
    {
      heading: "Khủng hoảng tài chính",
      content:
        "Nợ công tăng cao, nguồn thu không đủ bù chi khiến chính quyền quân chủ đứng trước nguy cơ phá sản [S1].",
      citation_ids: ["S1"]
    },
    {
      heading: "Thuế khóa bất công",
      content:
        "Tăng lữ và quý tộc được hưởng nhiều đặc quyền, còn nông dân, thợ thủ công và tư sản phải gánh phần lớn thuế khóa [S1].",
      citation_ids: ["S1"]
    },
    {
      heading: "Đời sống nhân dân khó khăn",
      content:
        "Mất mùa làm giá lương thực tăng, thất nghiệp và đói nghèo khiến mâu thuẫn xã hội thêm gay gắt [S1].",
      citation_ids: ["S1"]
    },
    {
      heading: "Tác động",
      content:
        "Khủng hoảng kinh tế – tài chính làm chế độ phong kiến suy yếu và góp phần thúc đẩy cách mạng bùng nổ năm 1789 [S1].",
      citation_ids: ["S1"]
    }
  ],
  key_points: [
    "Ngân khố gần phá sản vì nợ công và chi tiêu lớn.",
    "Đẳng cấp thứ ba chịu gánh nặng thuế khóa.",
    "Mất mùa và giá lương thực tăng làm đời sống nhân dân khó khăn.",
    "Khủng hoảng góp phần thúc đẩy Cách mạng tư sản Pháp năm 1789."
  ],
  citation_ids: ["S1"]
};

const mindmap = {
  title: "Khủng hoảng trước Cách mạng tư sản Pháp",
  nodes: [
    { id: "root", label: "Cách mạng Pháp 1789", description: "Khủng hoảng kinh tế – tài chính", type: "root" },
    { id: "cause-1", label: "Nợ công tăng cao", description: "Chiến tranh và chi tiêu cung đình làm ngân khố cạn kiệt", type: "cause", details: ["Nguồn thu không đủ bù chi", "Nhà nước đứng trước nguy cơ phá sản"] },
    { id: "cause-2", label: "Thuế khóa bất công", description: "Đẳng cấp thứ ba chịu phần lớn nghĩa vụ thuế", type: "cause", details: ["Tăng lữ và quý tộc có đặc quyền", "Nông dân và bình dân chịu gánh nặng"] },
    { id: "event-1", label: "Mất mùa 1788–1789", description: "Giá lương thực tăng và đời sống nhân dân khó khăn", type: "event", time: "1788–1789" },
    { id: "event-2", label: "Hội nghị Ba đẳng cấp", description: "Khủng hoảng buộc nhà vua triệu tập hội nghị", type: "event", time: "Tháng 5/1789" },
    { id: "person-1", label: "Louis XVI", description: "Nhà vua Pháp trong giai đoạn khủng hoảng", type: "person", people: ["Louis XVI"] },
    { id: "person-2", label: "Đẳng cấp thứ ba", description: "Lực lượng chịu thuế và đòi thay đổi xã hội", type: "person", people: ["Nông dân", "Bình dân", "Tư sản"] },
    { id: "meaning-1", label: "Chế độ phong kiến suy yếu", description: "Khủng hoảng làm mâu thuẫn xã hội gay gắt", type: "meaning" },
    { id: "meaning-2", label: "Thúc đẩy cách mạng", description: "Tạo điều kiện để cách mạng bùng nổ năm 1789", type: "meaning", memory_points: ["1789 – khủng hoảng – cách mạng"] }
  ],
  edges: [
    { source: "root", target: "cause-1" },
    { source: "root", target: "cause-2" },
    { source: "cause-1", target: "event-1" },
    { source: "cause-2", target: "event-2" },
    { source: "root", target: "person-1" },
    { source: "root", target: "person-2" },
    { source: "event-1", target: "meaning-1" },
    { source: "event-2", target: "meaning-2" }
  ]
};

const sources = [
  {
    id: "S1",
    title: "Bài 2 – Cách mạng tư sản Pháp cuối thế kỉ XVIII",
    publisher: "Kho dữ liệu HISEDU – Lịch sử 8",
    type: "dataset",
    grade: 8,
    page: null,
    page_status: "unverified",
    locator: "chapter_01/lesson_02/question_009",
    supports: ["Khủng hoảng tài chính", "Thuế khóa", "Đời sống nhân dân"],
    evidence_excerpt:
      "Nhà nước nợ nần, thuế khóa bất công và mất mùa làm mâu thuẫn xã hội ngày càng gay gắt.",
    review_status: "pending_teacher_review",
    provenance_note: "Số trang SGK chưa được xác minh trong metadata."
  }
];

const quizQuestions = [
  ["q1", "Nguyên nhân nào trực tiếp làm ngân khố Pháp gần cạn kiệt?", "remember", ["Chiến tranh và chi tiêu cung đình", "Công nghiệp phát triển quá nhanh", "Thuế bị xóa bỏ hoàn toàn", "Ngoại thương tăng mạnh"]],
  ["q2", "Đẳng cấp nào phải gánh phần lớn thuế khóa?", "remember", ["Đẳng cấp thứ ba", "Tăng lữ", "Quý tộc", "Hoàng gia"]],
  ["q3", "Vì sao mất mùa làm mâu thuẫn xã hội gay gắt hơn?", "understand", ["Giá lương thực tăng và đời sống khó khăn", "Nhà vua giảm thuế ngay", "Nợ công biến mất", "Đặc quyền phong kiến bị xóa bỏ"]],
  ["q4", "Khủng hoảng tài chính thể hiện hạn chế nào của chế độ cũ?", "understand", ["Thuế khóa bất công và chi tiêu thiếu kiểm soát", "Thiếu thuộc địa", "Không có nông nghiệp", "Không có giao thương"]],
  ["q5", "Nếu Đẳng cấp thứ ba tiếp tục chịu thuế nặng, hệ quả hợp lí nhất là gì?", "apply", ["Bất mãn xã hội tăng và yêu cầu cải cách mạnh hơn", "Mâu thuẫn tự biến mất", "Ngân khố lập tức cân bằng", "Đặc quyền phong kiến được ủng hộ hơn"]]
].map(([id, prompt, difficulty, labels]) => ({
  id,
  prompt,
  difficulty,
  options: labels.map((text, index) => ({ id: String.fromCharCode(97 + index), text }))
}));

const partial = {
  request_id: "evidence-local-partial",
  question: "Những khó khăn kinh tế và tài chính nào góp phần làm bùng nổ Cách mạng tư sản Pháp?",
  answer,
  mindmap,
  sources,
  limitations: ["Số trang SGK chưa được xác minh trong dữ liệu nguồn."]
};

const result = {
  ...partial,
  request_id: "evidence-local-final",
  answer_id: "answer-evidence-001",
  videos: [
    {
      title: "Cách mạng tư sản Pháp | Tóm tắt nhanh lịch sử thế giới – EZ Sử",
      url: "https://www.youtube.com/watch?v=t5fahfNM67w",
      publisher: "EZ Sử",
      relevance: "Tóm tắt đúng chủ đề Cách mạng tư sản Pháp và các nguyên nhân dẫn tới năm 1789.",
      label: "cause"
    }
  ],
  quiz: { quiz_id: "quiz-evidence", questions: quizQuestions },
  retrieval: {
    matched_ids: ["CHK_HIST8_CHUONG_1_BAI_2_CAU_09"],
    score_kind: "cosine",
    low_confidence: false
  }
};

const injectedFetch = `(() => {
  const originalFetch = window.fetch.bind(window);
  const answer = ${JSON.stringify(answer)};
  const mindmap = ${JSON.stringify(mindmap)};
  const sources = ${JSON.stringify(sources)};
  const partial = ${JSON.stringify(partial)};
  const result = ${JSON.stringify(result)};
  const quizQuestions = ${JSON.stringify(quizQuestions)};
  const jsonResponse = (body) => new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json; charset=utf-8" }
  });
  const sse = (payload) => "data: " + JSON.stringify(payload) + "\\n\\n";
  window.fetch = (input, init = {}) => {
    const url = typeof input === "string" ? input : input.url;
    if (url.includes("/api/questions/ocr")) {
      return Promise.resolve(jsonResponse({
        text: "Những khó khăn kinh tế và tài chính nào góp phần làm bùng nổ Cách mạng tư sản Pháp?",
        line_count: 2,
        mean_score: 0.96,
        needs_review: false
      }));
    }
    if (url.includes("/api/questions/ask-stream")) {
      const encoder = new TextEncoder();
      const stream = new ReadableStream({
        start(controller) {
          const events = [
            [20, { type: "progress", stage: "received", message: "Đã nhận câu hỏi và đang xác định chủ đề…" }],
            [650, { type: "progress", stage: "retrieval", message: "Đang tìm và đối chiếu nguồn trong kho kiến thức…" }],
            [1650, { type: "progress", stage: "enrichment", message: "Lời giải đã sẵn sàng; đang hoàn thiện mindmap, video và quiz…" }],
            [1700, { type: "partial_result", data: partial }],
            [3600, { type: "progress", stage: "finalizing", message: "Đang hoàn thiện các hoạt động ghi nhớ…" }],
            [4300, { type: "result", data: result }]
          ];
          for (const [wait, event] of events) {
            setTimeout(() => controller.enqueue(encoder.encode(sse(event))), wait);
          }
          setTimeout(() => controller.close(), 4350);
        }
      });
      return Promise.resolve(new Response(stream, {
        status: 200,
        headers: { "Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-cache" }
      }));
    }
    if (/\\/api\\/quizzes\\/[^/]+\\/answer/.test(url)) {
      const next = quizQuestions[1];
      return Promise.resolve(jsonResponse({
        quiz_id: "quiz-evidence",
        result: {
          question_id: "q1",
          selected_option_id: "a",
          correct: true,
          correct_option_id: "a",
          explanation: "Chiến tranh kéo dài và chi tiêu cung đình làm nợ công tăng, khiến ngân khố gần cạn kiệt [S1].",
          source_ids: ["S1"]
        },
        next_question: next,
        answered_count: 1,
        total_questions: 5,
        score_so_far: 1,
        completed: false,
        adaptive_message: "Chính xác! Câu tiếp theo sẽ nâng từ mức Nhớ lên mức Hiểu."
      }));
    }
    if (/\\/api\\/quizzes\\/[^/]+\\/reset/.test(url)) {
      return Promise.resolve(jsonResponse({ quiz_id: "quiz-evidence", questions: quizQuestions }));
    }
    return originalFetch(input, init);
  };
})();`;

class CdpClient {
  constructor(socket) {
    this.socket = socket;
    this.nextId = 1;
    this.pending = new Map();
    socket.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (!message.id) return;
      const waiter = this.pending.get(message.id);
      if (!waiter) return;
      this.pending.delete(message.id);
      if (message.error) waiter.reject(new Error(message.error.message));
      else waiter.resolve(message.result ?? {});
    });
  }

  call(method, params = {}) {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }
}

async function waitForDebugger() {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${debugPort}/json/list`);
      const pages = await response.json();
      const page = pages.find((item) => item.type === "page");
      if (page?.webSocketDebuggerUrl) return page.webSocketDebuggerUrl;
    } catch {}
    await delay(150);
  }
  throw new Error("Edge remote debugging did not become ready.");
}

async function evaluate(client, expression, awaitPromise = true) {
  const response = await client.call("Runtime.evaluate", {
    expression,
    awaitPromise,
    returnByValue: true,
    userGesture: true
  });
  if (response.exceptionDetails) throw new Error(response.exceptionDetails.text);
  return response.result?.value;
}

async function captureElement(client, fileName, finderExpression, maxHeight = 1350, topPadding = 18) {
  const rect = await evaluate(client, `(() => {
    const element = (${finderExpression});
    if (!element) return null;
    element.scrollIntoView({ block: "start", inline: "nearest" });
    const r = element.getBoundingClientRect();
    return {
      x: Math.max(0, r.left + window.scrollX - 18),
      y: Math.max(0, r.top + window.scrollY - ${topPadding}),
      width: Math.min(document.documentElement.scrollWidth, r.width + 36),
      height: Math.min(${maxHeight}, r.height + ${topPadding} + 18)
    };
  })()`);
  if (!rect) throw new Error(`Unable to find element for ${fileName}`);
  const shot = await client.call("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
    captureBeyondViewport: true,
    clip: { ...rect, scale: 1 }
  });
  await writeFile(path.join(outputDir, fileName), Buffer.from(shot.data, "base64"));
}

async function clickText(client, text) {
  const ok = await evaluate(client, `(() => {
    const target = [...document.querySelectorAll("button")].find((node) => node.textContent.includes(${JSON.stringify(text)}));
    if (!target) return false;
    target.click();
    return true;
  })()`);
  if (!ok) throw new Error(`Button not found: ${text}`);
}

const edge = spawn(edgePath, [
  "--headless=new",
  "--no-sandbox",
  "--disable-gpu",
  "--disable-software-rasterizer",
  "--disable-features=VizDisplayCompositor",
  "--hide-scrollbars",
  `--user-data-dir=${profilePath}`,
  `--remote-debugging-port=${debugPort}`,
  "--remote-allow-origins=*",
  "about:blank"
], { stdio: "ignore", windowsHide: true });

try {
  const socketUrl = await waitForDebugger();
  const socket = new WebSocket(socketUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
  const client = new CdpClient(socket);
  await client.call("Page.enable");
  await client.call("Runtime.enable");
  await client.call("Emulation.setDeviceMetricsOverride", {
    width: 1440,
    height: 1050,
    deviceScaleFactor: 1,
    mobile: false
  });
  await client.call("Page.addScriptToEvaluateOnNewDocument", { source: injectedFetch });
  await client.call("Page.navigate", { url: "http://127.0.0.1:3000" });
  await delay(2400);

  await evaluate(client, `(() => {
    const textarea = document.querySelector("#history-question");
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set;
    setter.call(textarea, "Những khó khăn kinh tế và tài chính nào góp phần làm bùng nổ Cách mạng tư sản Pháp?");
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
  })()`);
  await clickText(client, "Hỏi HISEDU");
  await delay(300);
  await captureElement(
    client,
    "06_loading_sse.png",
    `document.querySelector('section[aria-busy="true"]')`,
    950,
    80
  );

  await delay(1800);
  await captureElement(
    client,
    "08_partial_answer.png",
    `document.querySelector('div[aria-label="Kết quả học tập"]')`,
    1500
  );

  await delay(3000);
  await captureElement(
    client,
    "09_mindmap.png",
    `[...document.querySelectorAll('h2')].find((node) => node.textContent.trim() === 'Sơ đồ tư duy')?.closest('section')`,
    1300
  );
  await captureElement(
    client,
    "09_video.png",
    `[...document.querySelectorAll('h2')].find((node) => node.textContent.trim() === 'Xem để hiểu sâu hơn')?.closest('section')`,
    1100
  );
  await evaluate(client, `(async () => {
    const section = [...document.querySelectorAll('h2')]
      .find((node) => node.textContent.trim() === 'Tư liệu lịch sử xác thực')
      ?.closest('section');
    if (!section) return false;
    section.scrollIntoView({ block: "start", inline: "nearest" });
    const images = [...section.querySelectorAll('img')];
    images.forEach((img) => { img.loading = "eager"; });
    await Promise.race([
      Promise.all(images.map((img) => img.complete && img.naturalWidth > 0
        ? img.decode().catch(() => undefined)
        : new Promise((resolve) => {
            img.addEventListener("load", resolve, { once: true });
            img.addEventListener("error", resolve, { once: true });
          }))),
      new Promise((resolve) => setTimeout(resolve, 3000))
    ]);
    return true;
  })()`);
  await captureElement(
    client,
    "12_historical_images.png",
    `[...document.querySelectorAll('h2')].find((node) => node.textContent.trim() === 'Tư liệu lịch sử xác thực')?.closest('section')`,
    1300
  );

  await captureElement(
    client,
    "10_quiz_before.png",
    `[...document.querySelectorAll('h2')].find((node) => node.textContent.trim() === 'Quiz 5 câu')?.closest('section')`,
    1100
  );
  await evaluate(client, `(() => {
    const radio = document.querySelector('input[type="radio"]');
    radio?.click();
  })()`);
  await clickText(client, "Kiểm tra đáp án");
  await delay(500);
  await captureElement(
    client,
    "10_quiz_adaptive.png",
    `[...document.querySelectorAll('h2')].find((node) => node.textContent.trim() === 'Quiz 5 câu')?.closest('section')`,
    1300
  );

  await client.call("Page.navigate", { url: "http://127.0.0.1:3000" });
  await delay(2000);
  const documentNode = await client.call("DOM.getDocument", { depth: -1, pierce: true });
  const inputNode = await client.call("DOM.querySelector", {
    nodeId: documentNode.root.nodeId,
    selector: 'input[type="file"]'
  });
  await client.call("DOM.setFileInputFiles", {
    nodeId: inputNode.nodeId,
    files: [sampleImage]
  });
  await delay(700);
  await captureElement(
    client,
    "07_ocr_editable.png",
    `document.querySelector('section[aria-label="Đặt câu hỏi lịch sử"]')`,
    1250
  );
  socket.close();
  console.log("Captured local evidence screenshots without external API calls.");
} finally {
  edge.kill();
}
