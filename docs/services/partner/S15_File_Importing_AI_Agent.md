# Telcenter Partner - File Importing Service (S15)

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

Now, you are designing the **File Importing Service** service, in Python.
This service is inside the **Telcenter Partner** system.

Here are the peer services that the **File Importing Service** service may interact with:

- **S12 Partner Knowledge Update Service**: Forwards parsed file data for knowledge updates
- **S14 Metrics Service (Partner)**: Reports file import metrics and errors

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

### S12 Partner Knowledge Update Service

[HTTP API] - Forwards parsed knowledge data

### S14 Metrics Service (Partner)

[A34](../../api_groups/A34.md) - Sends import metrics

## The Flow

1. **Receive File Upload**: Accept file uploads via HTTP (Excel, CSV, or JSON formats containing telecom service information)

2. **Validate File Format**: Check file format, size limits, and required headers/structure

3. **Parse File Content**: Parse the file and extract telecom service data:
   - Service codes
   - Pricing information
   - Data quotas and speed tiers
   - Voice/SMS allowances
   - Registration syntax
   - Prerequisites and restrictions

4. **Data Transformation**: Transform parsed data into standardized format matching the expected schema

5. **Forward to Knowledge Update Service** (via A32): Send the parsed data to S12 for further processing

6. **Send Metrics** (via A34): Report import metrics (file size, records processed, errors, processing time)

7. **Return Import Results**: Return detailed import results including:
   - Number of records processed
   - Number of successful imports
   - Number of failures with error details
   - Validation warnings

If it fails at any stage, the whole process fails.
That is, immediately return error with the
appropriate error message.

## This Service's APIs

This service exposes the following APIs:

- [HTTP API] - File upload endpoint
  - Endpoint: `POST /api/v1/files/import`
  - Accepts: multipart/form-data with file attachment
  - Supported formats: .xlsx, .xls, .csv, .json

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

- Use pandas for Excel/CSV parsing
- Use openpyxl for Excel file handling
