# Telcenter Core - Knowledge Service (S03)

Introducing the series of Telcenter Engineering.

Telcenter, on the surface, is a semi-automated telecom services call center -
it is a web app that offers telecommunication services consultation. People
are serviced by the AI Agent, and they will be forwarded to in-person
consultants if the AI detected down mood, rage, or that it could not answer
the question itself given a pre-fed ground truth database. Now, we are
designing this as microservices. Telcenter Core would act as the main backend
for the end-user interface, and it consists of multiple microservices.
Telcenter Partner is another system that is deployed separately on each of
the telecom partner's servers, and it is responsible for taking up forwarded
conversations and continuing them with the real persons in-charge. Together,
one Core and several Partner systems cooperate to deliver the best customer
experience, while lowering cost dramatically, with the help of automated AI
responses.

The general deployment and communication topology is like this:

    Core <---(Internet)---> (Partner_1, Partner_2..., Partner_N)

The users' inquiries and answers to those are primarily in Vietnamese.

Now, you are designing the **Knowledge Service** service, in Python.
This service is inside the **Telcenter Core** system.

Here are the peer services that the **Knowledge Service** service may interact with:

- **S02 Consultant AI Agent**: The AI agent that handles customer conversations and queries the knowledge base for relevant information
- **S05 Knowledge Validator Service**: Validates and approves knowledge updates before they are stored in the knowledge database
- **S08 Metrics Service**: Queries the knowledge base for analytics and collects metrics about knowledge queries and usage patterns
- **S11 Partner Local Knowledge Service**: Receives metrics from partner services about knowledge queries

## A Note on API Transport Layers

The APIs of the services (including this one
and the peers) might be based on HTTP and/or
RabbitMQ transport protocols. One service might
also exposes multiple APIs of different kinds.

HTTP is mostly used in APIs that are exposed
to the frontend web apps, though it occasionally
is used for internal communication between
microservices, too. HTTP APIs are somewhat
RESTful (it is CRUD, stateless, versioned,
and HATEOAS, but it need not follow
Code-on-Demand requirements.)

For APIs that are based on RabbitMQ transport,
each API usually demands two queues, the
requests queue and the responses queue. The
caller would send requests into the former queue
and expect the responses to come out from the
latter. Exceptions will be explicitly noted.
The default queue names will be specified for
each such API. The queue names should be configurable
via `.env`, too.

## Peer Service APIs

Note that the base URL to call the services
must be specified via `.env`. Construct
a `.env.example` file for that.

### S02 Consultant AI Agent

[A01](../../api_groups/A01.md) - Receives knowledge updates from the AI Agent

### S05 Knowledge Validator Service

[A05](../../api_groups/A05.md) - Sends knowledge updates for validation before storing

### S08 Metrics Service

[A08](../../api_groups/A08.md) - Queries knowledge for analytics and receives metrics from this service

### S11 Partner Local Knowledge Service

[A08](../../api_groups/A08.md) - Receives metrics from partner knowledge queries

## The Flow

1. **Receive Knowledge Update Request** (via A01): The service receives a dataframe update request from the Consultant AI Agent containing telecom service information (packages, pricing, features, etc.)

2. **Validate Knowledge Update** (via A05): Forward the knowledge update to the Knowledge Validator Service for validation and approval

3. **Store Validated Knowledge**: Upon successful validation, store the knowledge in the Knowledge Database (vector database + structured database)

4. **Index for Search**: Update search indices and embeddings for efficient retrieval

5. **Send Metrics** (via A08): Report knowledge update metrics to the Metrics Service

6. **Return Success Response**: Acknowledge the successful update to the requesting service

If it fails at any stage, the whole process fails.
That is, immediately return error with the
appropriate error message.

## This Service's APIs

This service exposes the following APIs:

- [A01](../../api_groups/A01.md) - Receives knowledge updates from S02 Consultant AI Agent (RabbitMQ)
  - Request Queue: `telcenter_knowledge_requests`
  - Response Queue: `telcenter_knowledge_responses`

- [A08](../../api_groups/A08.md) - Query interface for other Core services to retrieve knowledge (RabbitMQ)
  - Request Queue: `telcenter_knowledge_query_requests`
  - Response Queue: `telcenter_knowledge_query_responses`

## Technology

- Python
- Use `uv` as the virtual environment and package manager.
- Multithreaded logic should be used for performance, since this
    component relies a lot on other services, which means the API calls
    to those services take up very much time. So this service is I/O bound.
    Note that, using multithreading to emulate async operations is very
    important - but do NOT use `async` and `await` in Python - that would
    be a mess!

- The class `MessageQueueService` must be used for RabbitMQ communication (which internally
    use `pika`).

    The class is [located in this file](../../../app/services/MessageQueueService.py).

    An example of using this class [is given here](../../MessageQueueService-usage-example.py).

    Also, for multithreading, only use the scheme in that file.
    Any other use of multithreading, if necessary, must strictly
    look for hazards - use locks and other synchronization primitives
    where appropriate.

- If this service needs to expose HTTP API(s), use Flask.

- The program entry point is [in this file](../../../app/__main__.py).

- Use ChromaDB or similar vector database for storing knowledge embeddings
- Use PostgreSQL for structured telecom service data
