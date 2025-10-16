import http from "k6/http";
import { check, sleep, group } from "k6";
import { Trend, Rate } from "k6/metrics";

// API 응답 시간 트렌드 / 실패율 메트릭
const homeDuration = new Trend("home_duration");
const certificateListDuration = new Trend("certificate_list_duration");
const certificateDetailDuration = new Trend("certificate_detail_duration");
const httpErrorRate = new Rate("http_errors");

export const options = {
  stages: [
    { duration: "30s", target: 10 }, // 예열
    { duration: "1m", target: 20 }, // 안정 구간
    { duration: "30s", target: 0 }, // 정리
  ],
  thresholds: {
    http_req_duration: ["p(95)<800"],
    http_errors: ["rate<0.05"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

export default function () {
  group("Public pages", () => {
    const homeRes = http.get(`${BASE_URL}/healthz`);
    homeDuration.add(homeRes.timings.duration);
    registerResult(homeRes, "healthz 200");

    const listRes = http.get(`${BASE_URL}/api/certificates/`);
    certificateListDuration.add(listRes.timings.duration);
    registerResult(listRes, "cert list 200");

    if (listRes.status === 200) {
      const results = listRes.json("results");
      if (Array.isArray(results) && results.length > 0) {
        const firstSlug = results[0].slug || results[0].id;
        if (firstSlug) {
          const detailRes = http.get(`${BASE_URL}/certificates/${firstSlug}/`);
          certificateDetailDuration.add(detailRes.timings.duration);
          registerResult(detailRes, "cert detail 200");
        }
      }
    }
  });

  sleep(1);
}

function registerResult(response, label) {
  const ok = check(response, {
    [label]: (res) => res.status === 200,
  });
  httpErrorRate.add(!ok);
}
