import http from "k6/http";
import { check, sleep } from "k6";
import { Trend, Rate } from "k6/metrics";

const boardListDuration = new Trend("board_list_duration");
const boardDetailDuration = new Trend("board_detail_duration");
const postCreateDuration = new Trend("post_create_duration");
const certificateSearchDuration = new Trend("certificate_search_duration");
const statsDuration = new Trend("certificate_stats_duration");
const httpErrorRate = new Rate("http_errors");

export const options = {
  scenarios: {
    browsePosts: {
      executor: "ramping-vus",
      exec: "browsePosts",
      stages: [
        { duration: "2m", target: 0 },
        { duration: "1m", target: 10 },
        { duration: "10m", target: 10 },
        { duration: "1m", target: 0 },
        { duration: "2m", target: 0 },
      ],
      gracefulRampDown: "30s",
    },
    
    createPost: {
      executor: "ramping-vus",
      exec: "createPost",
      stages: [
        { duration: "2m", target: 0 },
        { duration: "1m", target: 8 },
        { duration: "10m", target: 8 },
        { duration: "1m", target: 0 },
        { duration: "2m", target: 0 },
      ],
      gracefulRampDown: "30s",
    },
    searchCertificates: {
      executor: "ramping-vus",
      exec: "searchCertificates",
      stages: [
        { duration: "2m", target: 0 },
        { duration: "1m", target: 6 },
        { duration: "10m", target: 6 },
        { duration: "1m", target: 0 },
        { duration: "2m", target: 0 },
      ],
      gracefulRampDown: "30s",
    },
    viewStatistics: {
      executor: "ramping-vus",
      exec: "viewStatistics",
      stages: [
        { duration: "2m", target: 0 },
        { duration: "1m", target: 6 },
        { duration: "10m", target: 6 },
        { duration: "1m", target: 0 },
        { duration: "2m", target: 0 },
      ],
      gracefulRampDown: "30s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<800"],
    http_errors: ["rate<0.05"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8080";
const AUTH_TOKEN = __ENV.JWT_TOKEN || "";
const LOGIN_USERNAME = __ENV.TEST_USERNAME;
const LOGIN_PASSWORD = __ENV.TEST_PASSWORD;

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

export function browsePosts(data) {
  const listRes = http.get(`${BASE_URL}/api/posts/`);
  if (!track(boardListDuration, listRes, "posts list ok")) {
    sleep(1);
    return;
  }

  const results = listRes.json("results");
  if (Array.isArray(results) && results.length > 0) {
    const firstId = results[0].id;
    if (firstId) {
      const detailRes = http.get(`${BASE_URL}/api/posts/${firstId}/`);
      track(boardDetailDuration, detailRes, "post detail ok");
    }
  }

  sleep(1);
}

export function createPost(data) {
  const token = AUTH_TOKEN || (data && data.token);
  if (!token) {
    sleep(1);
    return;
  }

  const headers = {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
  const payload = JSON.stringify({
    title: `k6 게시글 ${Date.now()}`,
    body: "부하 테스트용 본문입니다.",
  });

  const createRes = http.post(`${BASE_URL}/api/posts/`, payload, { headers });
  if (!track(postCreateDuration, createRes, "post created", 201)) {
    sleep(3);
    return;
  }

  const createdId = createRes.json("id");
  if (createdId) {
    http.del(`${BASE_URL}/api/posts/${createdId}/`, null, { headers });
  }

  sleep(3);
}

export function searchCertificates(_data) {
  const res = http.get(`${BASE_URL}/api/certificates/?search=정보`);
  track(certificateSearchDuration, res, "certificate search ok");
  sleep(1);
}

export function viewStatistics(_data) {
  const res = http.get(`${BASE_URL}/api/statistics/`);
  track(statsDuration, res, "certificate stats ok");
  sleep(1);
}
