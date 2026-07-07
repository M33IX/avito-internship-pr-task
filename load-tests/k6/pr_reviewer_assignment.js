import http from "k6/http";
import { check, group, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8080";
const WORKLOAD = __ENV.WORKLOAD || "api_mix";
const START_RATE = Number(__ENV.START_RATE || "1");
const TARGET_RATE = Number(__ENV.TARGET_RATE || "20");
const DURATION = __ENV.DURATION || "5m";
const RAMP_UP = __ENV.RAMP_UP || "1m";
const RAMP_DOWN = __ENV.RAMP_DOWN || "30s";
const PRE_ALLOCATED_VUS = Number(__ENV.PRE_ALLOCATED_VUS || "50");
const MAX_VUS = Number(__ENV.MAX_VUS || "200");
const SLEEP_MS = Number(__ENV.SLEEP_MS || "100");
const SLO_P95_MS = Number(__ENV.SLO_P95_MS || "300");
const SLI_TEAMS = Number(__ENV.SLI_TEAMS || "20");
const SLI_USERS_PER_TEAM = Number(__ENV.SLI_USERS_PER_TEAM || "10");
const SLI_SEED_PRS = Number(__ENV.SLI_SEED_PRS || "100");
const RUN_ID = (__ENV.RUN_ID || Date.now().toString(36)).slice(-5);
const REASSIGN_EXPECTED_STATUSES = http.expectedStatuses(
  { min: 200, max: 399 },
  409,
);

function workloadScenarios() {
  const baseScenario = {
    executor: "ramping-arrival-rate",
    startRate: START_RATE,
    timeUnit: "1s",
    preAllocatedVUs: PRE_ALLOCATED_VUS,
    maxVUs: MAX_VUS,
    stages: [
      { duration: RAMP_UP, target: TARGET_RATE },
      { duration: DURATION, target: TARGET_RATE },
      { duration: RAMP_DOWN, target: 0 },
    ],
  };

  if (WORKLOAD === "smoke") {
    return {
      smoke: {
        ...baseScenario,
        exec: "apiMixFlow",
        stages: [
          { duration: "10s", target: 1 },
          { duration: "20s", target: 1 },
          { duration: "10s", target: 0 },
        ],
      },
    };
  }

  if (WORKLOAD === "deactivate") {
    return {
      deactivate: {
        ...baseScenario,
        exec: "deactivateFlow",
      },
    };
  }

  if (WORKLOAD === "sli") {
    return {
      sli: {
        ...baseScenario,
        exec: "sliFlow",
      },
    };
  }

  return {
    api_mix: {
      ...baseScenario,
      exec: "apiMixFlow",
    },
  };
}

export const options = {
  scenarios: workloadScenarios(),
  thresholds: {
    "http_req_failed{phase:load}": ["rate<0.01"],
    "http_req_duration{phase:load}": [`p(95)<${SLO_P95_MS}`],
    "http_req_duration{phase:load,endpoint:health}": ["p(95)<200"],
    "http_req_duration{phase:load,endpoint:create_pr}": [
      `p(95)<${SLO_P95_MS}`,
    ],
    "http_req_duration{phase:load,endpoint:deactivate_team}": ["p(95)<1500"],
  },
};

function randomBase36(length) {
  const max = 36 ** length;
  return Math.floor(Math.random() * max)
    .toString(36)
    .padStart(length, "0");
}

function uniqueSuffix() {
  const vu = String(__VU || 0);
  const iteration = String(__ITER || 0);
  return `${RUN_ID}${vu}${iteration}${randomBase36(3)}`.slice(0, 12);
}

function jsonHeaders(endpoint, options = {}) {
  const phase = options.phase || "load";
  const params = {
    headers: {
      "Content-Type": "application/json",
    },
    tags: {
      endpoint,
      name: endpoint,
      phase,
    },
  };

  if (options.responseCallback) {
    params.responseCallback = options.responseCallback;
  }

  return params;
}

function getParams(endpoint, phase = "load") {
  return {
    tags: {
      endpoint,
      name: endpoint,
      phase,
    },
  };
}

function postJson(path, payload, endpoint, options = {}) {
  return http.post(
    `${BASE_URL}${path}`,
    JSON.stringify(payload),
    jsonHeaders(endpoint, options),
  );
}

function addTeam(teamName, members, phase = "load") {
  const response = postJson(
    "/team/add",
    {
      team_name: teamName,
      members,
    },
    "add_team",
    { phase },
  );

  check(response, {
    "team/add status is 201": (r) => r.status === 201,
  });
  return response;
}

function createTeamPayload(suffix, teamPrefix = "t") {
  const teamName = `${teamPrefix}${suffix}`;
  return {
    teamName,
    authorId: `a${suffix}`,
    reviewerOneId: `b${suffix}`,
    reviewerTwoId: `c${suffix}`,
    reviewerThreeId: `d${suffix}`,
    members: [
      { user_id: `a${suffix}`, username: "Author", is_active: true },
      { user_id: `b${suffix}`, username: "Reviewer One", is_active: true },
      { user_id: `c${suffix}`, username: "Reviewer Two", is_active: true },
      { user_id: `d${suffix}`, username: "Reviewer Three", is_active: true },
    ],
  };
}

function createReplacementTeamPayload(suffix) {
  const teamName = `x${suffix}`;
  return {
    teamName,
    replacementOneId: `e${suffix}`,
    replacementTwoId: `f${suffix}`,
    members: [
      { user_id: `e${suffix}`, username: "Replacement One", is_active: true },
      { user_id: `f${suffix}`, username: "Replacement Two", is_active: true },
    ],
  };
}

function createPullRequest(pullRequestId, authorId, phase = "load") {
  const response = postJson(
    "/pullRequest/create",
    {
      pull_request_id: pullRequestId,
      pull_request_name: "Load test PR",
      author_id: authorId,
    },
    "create_pr",
    { phase },
  );

  check(response, {
    "pullRequest/create status is 201": (r) => r.status === 201,
  });
  return response;
}

function parseJson(response) {
  try {
    return response.json();
  } catch (_error) {
    return null;
  }
}

function pause() {
  if (SLEEP_MS > 0) {
    sleep(SLEEP_MS / 1000);
  }
}

function randomItem(items) {
  return items[Math.floor(Math.random() * items.length)];
}

export function setup() {
  if (WORKLOAD !== "sli") {
    return null;
  }

  const teams = [];
  const users = [];
  const seededPullRequests = [];

  for (let teamIndex = 0; teamIndex < SLI_TEAMS; teamIndex += 1) {
    const teamName = `s${RUN_ID}${teamIndex.toString(36)}`;
    const members = [];
    for (let userIndex = 0; userIndex < SLI_USERS_PER_TEAM; userIndex += 1) {
      const userId = `u${teamIndex.toString(36)}${userIndex.toString(36)}${RUN_ID}`;
      const user = {
        user_id: userId,
        username: `User ${teamIndex}-${userIndex}`,
        is_active: true,
        team_name: teamName,
      };
      members.push({
        user_id: user.user_id,
        username: user.username,
        is_active: user.is_active,
      });
      users.push(user);
    }

    addTeam(teamName, members, "setup");
    teams.push({
      teamName,
      users: members.map((member) => member.user_id),
    });
  }

  for (let index = 0; index < SLI_SEED_PRS; index += 1) {
    const team = teams[index % teams.length];
    const authorId = randomItem(team.users);
    const pullRequestId = `r${RUN_ID}${index.toString(36)}`;
    const response = createPullRequest(pullRequestId, authorId, "setup");
    const payload = parseJson(response);
    seededPullRequests.push({
      pullRequestId,
      reviewers: payload?.pr?.assigned_reviewers || [],
    });
  }

  return {
    teams,
    users,
    seededPullRequests,
  };
}

export function sliFlow(data) {
  const action = Math.random();

  if (action < 0.35) {
    const user = randomItem(data.users);
    createPullRequest(`p${uniqueSuffix()}`, user.user_id);
    return;
  }

  if (action < 0.55) {
    const team = randomItem(data.teams);
    const response = http.get(
      `${BASE_URL}/team/get?team_name=${team.teamName}`,
      getParams("get_team"),
    );
    check(response, {
      "team/get status is 200": (r) => r.status === 200,
    });
    return;
  }

  if (action < 0.75) {
    const user = randomItem(data.users);
    const response = http.get(
      `${BASE_URL}/users/getReview?user_id=${user.user_id}`,
      getParams("get_review"),
    );
    check(response, {
      "users/getReview status is 200": (r) => r.status === 200,
    });
    return;
  }

  if (action < 0.90) {
    const pullRequest = randomItem(data.seededPullRequests);
    const response = postJson(
      "/pullRequest/merge",
      {
        pull_request_id: pullRequest.pullRequestId,
      },
      "merge_pr",
    );
    check(response, {
      "pullRequest/merge status is 200": (r) => r.status === 200,
    });
    return;
  }

  const pullRequest = randomItem(data.seededPullRequests);
  const oldUserId = randomItem(pullRequest.reviewers);
  if (!oldUserId) {
    return;
  }

  const response = postJson(
    "/pullRequest/reassign",
    {
      pull_request_id: pullRequest.pullRequestId,
      old_user_id: oldUserId,
    },
    "reassign_pr",
    { responseCallback: REASSIGN_EXPECTED_STATUSES },
  );
  check(response, {
    "pullRequest/reassign status is 200 or 409": (r) =>
      r.status === 200 || r.status === 409,
  });
}

export function apiMixFlow() {
  const suffix = uniqueSuffix();
  const team = createTeamPayload(suffix);
  const pullRequestId = `p${suffix}`;

  group("create and read", () => {
    addTeam(team.teamName, team.members);
    pause();

    const createdPr = createPullRequest(pullRequestId, team.authorId);
    const createdPrPayload = parseJson(createdPr);
    pause();

    const teamResponse = http.get(
      `${BASE_URL}/team/get?team_name=${team.teamName}`,
      getParams("get_team"),
    );
    check(teamResponse, {
      "team/get status is 200": (r) => r.status === 200,
    });

    const reviewers = createdPrPayload?.pr?.assigned_reviewers || [];
    if (reviewers.length > 0) {
      const reviewResponse = http.get(
        `${BASE_URL}/users/getReview?user_id=${reviewers[0]}`,
        getParams("get_review"),
      );
      check(reviewResponse, {
        "users/getReview status is 200": (r) => r.status === 200,
      });
    }
  });

  group("mutate pr", () => {
    const prResponse = http.get(
      `${BASE_URL}/users/getReview?user_id=${team.reviewerOneId}`,
      getParams("get_review"),
    );
    check(prResponse, {
      "users/getReview before mutate is 200": (r) => r.status === 200,
    });

    const createdPr = createPullRequest(`q${suffix}`, team.authorId);
    const reviewers = parseJson(createdPr)?.pr?.assigned_reviewers || [];
    if (reviewers.length > 0) {
      const reassignResponse = postJson(
        "/pullRequest/reassign",
        {
          pull_request_id: `q${suffix}`,
          old_user_id: reviewers[0],
        },
        "reassign_pr",
        { responseCallback: REASSIGN_EXPECTED_STATUSES },
      );
      check(reassignResponse, {
        "pullRequest/reassign status is 200 or 409": (r) =>
          r.status === 200 || r.status === 409,
      });
    }

    const mergeResponse = postJson(
      "/pullRequest/merge",
      {
        pull_request_id: `q${suffix}`,
      },
      "merge_pr",
    );
    check(mergeResponse, {
      "pullRequest/merge status is 200": (r) => r.status === 200,
    });
  });
}

export function deactivateFlow() {
  const suffix = uniqueSuffix();
  const team = createTeamPayload(suffix);
  const replacementTeam = createReplacementTeamPayload(suffix);
  const pullRequestId = `p${suffix}`;

  group("deactivate team safely", () => {
    addTeam(team.teamName, [
      { user_id: team.authorId, username: "Author", is_active: true },
      { user_id: team.reviewerOneId, username: "Reviewer One", is_active: true },
      { user_id: team.reviewerTwoId, username: "Reviewer Two", is_active: true },
    ]);
    addTeam(replacementTeam.teamName, replacementTeam.members);
    createPullRequest(pullRequestId, team.authorId);
    pause();

    const response = postJson(
      "/team/deactivate",
      {
        team_name: team.teamName,
        replacement_team_name: replacementTeam.teamName,
      },
      "deactivate_team",
    );

    check(response, {
      "team/deactivate status is 200": (r) => r.status === 200,
      "team/deactivate has reassignments": (r) => {
        const payload = parseJson(r);
        return (payload?.reassignments || []).length > 0;
      },
    });
  });
}

export default function () {
  apiMixFlow();
}
