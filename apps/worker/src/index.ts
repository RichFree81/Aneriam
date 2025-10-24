import { type JobsOptions, Queue, Worker } from "bullmq";

const redisConnection = {
  host: process.env.REDIS_HOST ?? "127.0.0.1",
  port: Number.parseInt(process.env.REDIS_PORT ?? "6379", 10)
};

const defaultJobOptions: JobsOptions = {
  removeOnComplete: true,
  attempts: 3,
  backoff: {
    type: "exponential",
    delay: 1000
  }
};

const exampleQueue = new Queue("example", {
  connection: redisConnection,
  defaultJobOptions
});

const exampleWorker = new Worker(
  "example",
  async job => {
    // Placeholder job processor; replace with domain logic.
    console.log(`[worker] processing job ${job.id}`, job.data);
  },
  {
    connection: redisConnection
  }
);

exampleWorker.on("completed", job => {
  console.log(`[worker] job ${job.id} completed`);
});

exampleWorker.on("failed", (job, err) => {
  console.error(`[worker] job ${job?.id ?? "unknown"} failed`, err);
});

async function main() {
  console.log("[worker] booting Aneriam worker");

  if (process.env.SEED_DEMO_JOB === "true") {
    await exampleQueue.add("demo", { hello: "world" });
    console.log("[worker] seeded demo job");
  }
}

main().catch(error => {
  console.error("[worker] fatal error", error);
  process.exitCode = 1;
});

const shutdown = async () => {
  console.log("[worker] shutting down");
  await Promise.all([exampleWorker.close(), exampleQueue.close()]);
  process.exit(0);
};

process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
