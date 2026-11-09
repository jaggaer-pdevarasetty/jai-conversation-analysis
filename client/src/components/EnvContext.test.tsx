import { renderToString } from "react-dom/server";
import { persistEnv } from "../services/env";
import { EnvProvider, useEnv } from "./EnvContext";

jest.mock("../services/dashboardApi", () => ({
  fetchEnvironments: jest.fn(),
}));

function EnvProbe() {
  return <span>{useEnv().env}</span>;
}

describe("EnvProvider hydration", () => {
  afterEach(() => persistEnv("uit"));

  it("uses the same UIT value for the server and first client render", () => {
    persistEnv("prod");
    expect(renderToString(<EnvProvider><EnvProbe /></EnvProvider>)).toContain("uit");
  });
});
