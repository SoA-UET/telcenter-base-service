# Telcenter Partner - Partner Local Knowledge Service (S11)

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

Now, you are designing the **Partner Local Knowledge Service** service, in Python.
This service is inside the **Telcenter Partner** system.

Here are the peer services that the **Partner Local Knowledge Service** service may interact with:

- **S13 Partner Consultation Service**: Provides knowledge base access for partner consultants handling forwarded conversations
- **S12 Partner Knowledge Update Service**: Receives knowledge updates from Core system
- **S08 Core Metrics Service**: Reports knowledge query metrics to Core system
- **S14 Partner Metrics Service**: Reports knowledge query metrics to Partner system

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

### S13 Partner Consultation Service

[A16](../../api_groups/A16.md) - Provides knowledge query interface for consultants

### S12 Partner Knowledge Update Service

[A33](../../api_groups/A33.md) - Receives knowledge updates from Core

### S08 Core Metrics Service

[A08](../../api_groups/A08.md) - Sends query metrics to Core

### S14 Partner Metrics Service

[A34](../../api_groups/A34.md) - Sends query metrics to Partner

## The Flow

1. **Receive Knowledge Query** (via A16): Consultant service requests relevant knowledge based on customer query

2. **Search Local Knowledge Base**: Query the local vector database and structured database for relevant telecom service information

3. **Rank and Filter Results**: Rank results by relevance and filter based on partner-specific configurations

4. **Format Response**: Format the knowledge in a consultant-friendly format with relevant service details, pricing, and procedures

5. **Send Metrics to Core** (via A08): Report query metrics to S08 Core Metrics Service

6. **Send Metrics to Partner** (via A34): Report query metrics to S14 Partner Metrics Service

7. **Return Knowledge Results**: Send formatted knowledge back to the requesting consultant service

If it fails at any stage, the whole process fails.
That is, immediately return error with the
appropriate error message.

## This Service's APIs

This service exposes the following APIs:

- [A16](../../api_groups/A16.md) - Query interface for S13 Partner Consultation Service (RabbitMQ)
  - Request Queue: `partner_knowledge_query_requests`
  - Response Queue: `partner_knowledge_query_responses`

- [A33](../../api_groups/A33.md) - Receives knowledge updates from S12 (RabbitMQ)
  - Request Queue: `partner_knowledge_update_requests`
  - Response Queue: `partner_knowledge_update_responses`

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

- Use ChromaDB or similar vector database for local knowledge storage
- Use SQLite for lightweight structured data storage on partner premises
