import http from "k6/http";
import { check, sleep } from "k6";
import { Trend, Rate } from "k6/metrics";

const chatDuration = new Trend("chat_duration");
const httpErrorRate = new Rate("http_errors");

export const options = {
  scenarios: {
    chatApi: {
      executor: "ramping-vus",
      exec: "chatApi",
      stages: [
        { duration: "1m", target: 0 },
        { duration: "1m", target: 5 },
        { duration: "2m", target: 20 },
        { duration: "5m", target: 20 },
        { duration: "1m", target: 5 },
        { duration: "1m", target: 0 },
      ],
      gracefulRampDown: "30s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_errors: ["rate<0.05"],
    chat_duration: ["p(95)<1500"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8080";
const AUTH_TOKEN = __ENV.JWT_TOKEN || "";
const LOGIN_USERNAME = __ENV.TEST_USERNAME;
const LOGIN_PASSWORD = __ENV.TEST_PASSWORD;
const CHAT_API_ENABLED = String(__ENV.CHAT_API_ENABLED || "false").toLowerCase() === "true";
const MOCK_CHAT_PATH = __ENV.MOCK_CHAT_PATH || "/api/posts/";

function track(trend, response, label, expectedStatus = 200) {
  if (trend) {
    trend.add(response.timings.duration);
  }
  const ok = check(response, {
    [label]: (res) =>
      Array.isArray(expectedStatus) ? expectedStatus.includes(res.status) : res.status === expectedStatus,
  });
  httpErrorRate.add(!ok);
  return ok;
}

export function setup() {
  if (AUTH_TOKEN) {
    return { token: AUTH_TOKEN };
  }

  if (!LOGIN_USERNAME || !LOGIN_PASSWORD) {
    return { token: "" };
  }

  const payload = JSON.stringify({
    username: LOGIN_USERNAME,
    password: LOGIN_PASSWORD,
  });

  const res = http.post(`${BASE_URL}/api/users/token/`, payload, {
    headers: { "Content-Type": "application/json" },
  });

  if (!track(null, res, "token obtain ok", [200])) {
    return { token: "" };
  }

  const token = res.json("access");
  if (!token) {
    return { token: "" };
  }

  return { token };
}

const sampleQuestions = [
  "자격증 공부를 시작하는데 어떤 순서가 좋을까요?",
  "데이터 분석 초보에게 추천할 만한 자격증이 있을까요?",
  "AI 분야 이직을 준비 중인데 필요한 스킬을 알려줘.",
  "올해 인기 있는 IT 자격증 동향 좀 알려주세요.",
];

export function chatApi(data) {
  if (!CHAT_API_ENABLED) {
    const res = http.get(`${BASE_URL}${MOCK_CHAT_PATH}`);
    track(chatDuration, res, "mock chat ok");
    sleep(1);
    return;
  }

  const token = AUTH_TOKEN || (data && data.token);
  if (!token) {
    sleep(1);
    return;
  }

  const headers = {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
  const message = sampleQuestions[Math.floor(Math.random() * sampleQuestions.length)];
  const payload = JSON.stringify({
    message,
    history: [{ role: "user", content: "지난번에 추천받은 내용 정리해줘" }],
    temperature: 0.3,
  });

  const res = http.post(`${BASE_URL}/api/ai/chat/`, payload, { headers });
  track(chatDuration, res, "chat reply ok");
  sleep(2);
}
