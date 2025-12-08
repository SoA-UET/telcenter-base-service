# Telcenter Core - Knowledge Validator Service (S05)

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

Now, you are designing the **Knowledge Validator Service** service, in Python.
This service is inside the **Telcenter Core** system.

Here are the peer services that the **Knowledge Validator Service** service may interact with:

- **S03 Knowledge Service**: Receives knowledge validation requests and sends back validation results
- **S08 Metrics Service**: Reports validation metrics and quality scores

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

### S03 Knowledge Service

[A05](../../api_groups/A05.md) - Receives validation requests from Knowledge Service

### S08 Metrics Service

[A08](../../api_groups/A08.md) - Reports validation metrics and quality scores

## The Flow

1. **Receive Validation Request** (via A05): The service receives a knowledge validation request containing telecom service data to be validated

2. **Schema Validation**: Validate that the data conforms to the expected schema (required fields, data types, value ranges)

3. **Business Rule Validation**: Check business rules:
   - Pricing must be positive
   - Cycle duration must be valid (e.g., 1, 7, 30, 90, 365 days)
   - Service codes must follow naming conventions
   - Data quotas must be reasonable values

4. **Duplicate Detection**: Check if similar service information already exists in the knowledge base

5. **Data Quality Scoring**: Calculate a quality score based on completeness, consistency, and accuracy

6. **Send Metrics** (via A08): Report validation results and quality scores to Metrics Service

7. **Return Validation Result**: Send validation status (approved/rejected) with details back to Knowledge Service

If it fails at any stage, the whole process fails.
That is, immediately return error with the
appropriate error message.

## This Service's APIs

This service exposes the following APIs:

- [A05](../../api_groups/A05.md) - Receives validation requests from S03 Knowledge Service (RabbitMQ)
  - Request Queue: `telcenter_knowledge_validation_requests`
  - Response Queue: `telcenter_knowledge_validation_responses`

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

- Use Pydantic for schema validation
