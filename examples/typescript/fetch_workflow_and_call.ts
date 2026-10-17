// Fetch a workflow by ID and place a test phone call using the TypeScript SDK.
//
// Requirements:
//   npm install @easytech/sdk
//
// Environment variables:
//   EASYTECH_API_ENDPOINT  - EasyTech API base URL (e.g. http://localhost:8000)
//   EASYTECH_API_TOKEN     - API token sent as X-API-Key
//
// Run:
//   npx tsx fetch_workflow_and_call.ts

import { EasyTechClient } from "@easytech/sdk";

// Numeric workflow ID to fetch and call with.
const WORKFLOW_ID = 1;
// E.164 destination number — set this to the number you want to call.
const PHONE_NUMBER = "+11187619471";

async function main(): Promise<void> {
    const apiEndpoint = process.env.EASYTECH_API_ENDPOINT ?? "http://localhost:8000";
    const apiToken = process.env.EASYTECH_API_TOKEN;

    if (!apiToken) throw new Error("EASYTECH_API_TOKEN is required");

    const client = new EasyTechClient({
        baseUrl: apiEndpoint,
        apiKey: apiToken,
    });

    const workflow = await client.getWorkflow(WORKFLOW_ID);
    console.log(
        `Fetched workflow ${workflow.id}: ${JSON.stringify(workflow.name)} (status=${workflow.status})`,
    );

    const response = await client.testPhoneCall({
        body: {
            workflow_id: WORKFLOW_ID,
            phone_number: PHONE_NUMBER,
        },
    });
    console.log("Call initiated:", response);
}

main().catch((err) => {
    console.error(err);
    process.exit(1);
});
