# Thinx – Identified Limitations

## 1. Data formatting and data quality limitations

A major limitation is that the platform is sensitive to differences in how input data is formatted. Data that is technically valid can be lost or interpreted incorrectly when its format does not match the exact format expected by the processing pipeline.

### Date formatting can cause data loss

The processing pipeline originally recognized only a limited set of date formats when calculating age. Dates stored as text in the form `YYYY-MM-DD`, such as `2023-04-25`, were not interpreted correctly.

As a result:

- victim ages were converted to `not specified`;
- the age value could not be converted to the expected integer datatype;
- the corresponding RDF value was silently dropped;
- the Age column appeared empty in queries and in the Data Viewer.


## 2. Inconsistent categorical values

The assessments also identify inconsistent nationality values. Some records use demonyms, such as `Ethiopian`, while others use country names, such as `Somalia`.

This causes problems when grouping, filtering, or aggregating records because values that represent the same type of information are not expressed using a consistent convention. The app would benefit from validation and normalization rules during import, for example by mapping all nationality values to an agreed controlled vocabulary.

## 3. Incorrect transformation of trafficker data

Trafficker names can be transformed incorrectly during RDF generation. The transformation logic expects a list of names but can receive a single string instead. The string is then treated as an iterable and split into individual characters.

Consequences include:

- incorrect relationships between victims and traffickers;
- incorrect trafficker counts;
- unreliable aggregations involving traffickers;
- potentially incorrect incident statistics.

This is particularly problematic because the application may continue to operate normally while presenting structurally incorrect data.

## 4. Silent failures reduce trust in the displayed data

Several failures are not clearly communicated to the user.

For example, when database credentials were incorrect, the Data Viewer displayed `0 victims`, `0 incidents`, and `0 triples` instead of clearly reporting that the database connection had failed.

Similarly, invalid or unsupported values can be dropped during processing without an obvious warning.

This makes it difficult for researchers to distinguish between:

- a genuinely empty dataset;
- incorrectly formatted input;
- failed data conversion;
- a failed database connection.


## 5. Non-deterministic processing

`borders_crossed` is constructed from a Python set. Since set ordering is not guaranteed, the order of values can change between runs.

Where another value, such as an extortion amount, is matched to a border based on position, this can result in the amount being associated with the wrong border.

The same input should produce the same structured output every time. Non-deterministic transformations make reproducibility and verification difficult.

## 6. Limited analytical functionality in the user interface

The platform includes a Data Viewer and supports queries against the underlying RDF data. However, the provided assessment material mainly describes the interface as a way to **view records, counts, and query results**.

The findings do not document a substantial built-in analytical layer for researchers, such as:

- interactive aggregation and grouping;
- configurable charts and visualizations;
- statistical summaries;
- cross-variable comparisons;
- trend analysis;
- reusable analytical dashboards;
- guided filtering and exploration;
- automatic identification of patterns or anomalies.

Some analysis is technically possible through SPARQL queries and backend/federated query code, but this requires users to formulate queries or rely on predefined technical logic rather than performing analysis directly through the interface.

Therefore, from an end-user perspective, the current platform functions more as a **data ingestion, storage, querying, and viewing system** than as a complete data-analysis environment.

## 7. Data quality problems directly affect analysis

The lack of strong validation is especially important because analytical functionality depends on consistent underlying data.

For example:

- missing ages make age averages incomplete or misleading;
- inconsistent nationality values distort grouped statistics;
- malformed trafficker names invalidate trafficker-based counts;
- incorrect border-to-payment relationships can produce false conclusions.

Adding more analytical features without first improving the validation and normalization pipeline could make these problems less visible while giving users greater confidence in incorrect results.
