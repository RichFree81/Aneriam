import { describe, expect, it } from "vitest";

import { AppController } from "./app.controller";
import { AppService } from "./app.service";

describe("AppController", () => {
  it('should return "Hello World!"', () => {
    const appController = new AppController(new AppService());

    expect(appController.getHello()).toBe("Hello World!");
  });
});
