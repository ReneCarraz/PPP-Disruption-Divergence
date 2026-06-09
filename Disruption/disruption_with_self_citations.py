from google.cloud import bigquery
import time
import tqdm
import re

class Disruption():

  def __init__(self, project, dataset, table_id, table_out, var_id, Y,
               var_refs, var_year, source_data, source_id, aggregated_ref=True,
               patent=False, year_table=False, citation_category=None, to_concat_before = ''):

    self.client = bigquery.Client()
    self.project = project
    self.dataset = dataset
    self.table_id = table_id
    self.table_out = table_out
    self.var_id = var_id
    self.Y = Y
    self.var_refs = var_refs
    self.var_year = var_year
    self.source_data = source_data
    self.source_id = source_id
    self.aggregated = aggregated_ref
    self.year_table = year_table
    self.patent = patent
    self.citation_category = citation_category

    if patent:
      self.data_to_search = """data_to_search AS (
            SELECT DISTINCT
              REPLACE({var_id}, 'US-', '') AS id,
            FROM
              `{project}.{dataset}.{table_id}`
          )""".format(var_id = self.var_id,
                      project = self.project,
                      dataset = self.dataset,
                      table_id = self.table_id)

    else:
      if to_concat_before:
        self.data_to_search = """data_to_search AS (
          SELECT DISTINCT
            CONCAT({to_concat_before}, {var_id}) AS id,
          FROM
            `{project}.{dataset}.{table_id}`
        )""".format(var_id = self.var_id,
                        project = self.project,
                        dataset = self.dataset,
                        table_id = self.table_id,
                        to_concat_before = to_concat_before)
      else:
         self.data_to_search = """data_to_search AS (
          SELECT DISTINCT {var_id} AS id,
          FROM
            `{project}.{dataset}.{table_id}`
        )""".format(var_id = self.var_id,
                        project = self.project,
                        dataset = self.dataset,
                        table_id = self.table_id)
    self.citation_filter = ""
    if patent and citation_category:
      self.citation_filter = f"AND citation_category = '{citation_category}'"

    # Construction des templates initial_works et cit_works
    if year_table:
      if self.aggregated:
        initial_works_template = """initial_works AS (
            SELECT
              t1.{source_id} AS id,
              t1.{var_refs},
              CAST(SUBSTR(CAST(t2.{var_year} AS STRING), 1, 4) AS INT64) AS {var_year}
            FROM
              `{source_data}` t1
            JOIN
              `{year_table}` t2
            ON
              t1.{source_id} = t2.{source_id}
            WHERE
              t1.{var_refs} IS NOT NULL
              AND ARRAY_LENGTH(t1.{var_refs}) > 0
              AND t1.{source_id} IN (SELECT id FROM chunked_data)
              {citation_filter}
            GROUP BY t1.{source_id}, t1.{var_refs}, CAST(SUBSTR(CAST(t2.{var_year} AS STRING), 1, 4) AS INT64)
          )"""

        cit_works_template = """cit_works AS (
            SELECT
              w.{source_id} AS id,
              w.{var_refs},
              CAST(SUBSTR(CAST(y.{var_year} AS STRING), 1, 4) AS INT64) AS {var_year}
            FROM
              `{source_data}` w
            JOIN
              `{year_table}` y
            ON
              w.{source_id} = y.{source_id},
            UNNEST(w.{var_refs}) AS ref_id
            WHERE
              w.{var_refs} IS NOT NULL
              AND ARRAY_LENGTH(w.{var_refs}) > 0
              AND ref_id IN (SELECT id FROM initial_works)
            GROUP BY w.{source_id}, w.{var_refs}, CAST(SUBSTR(CAST(y.{var_year} AS STRING), 1, 4) AS INT64)
          )"""
      else:
        initial_works_template = """initial_works AS (
            SELECT
              t1.{source_id} AS id,
              ARRAY_AGG(t1.{var_refs}) AS {var_refs},
              CAST(SUBSTR(CAST(t2.{var_year} AS STRING), 1, 4) AS INT64) AS {var_year}
            FROM
              `{source_data}` t1
            JOIN
              `{year_table}` t2
            ON
              t1.{source_id} = t2.{source_id}
            WHERE
              t1.{var_refs} IS NOT NULL
              AND t1.{source_id} IN (SELECT id FROM chunked_data)
              {citation_filter}
            GROUP BY t1.{source_id}, CAST(SUBSTR(CAST(t2.{var_year} AS STRING), 1, 4) AS INT64)
          )"""

        cit_works_template = """cit_works AS (
            SELECT
              w.{source_id} AS id,
              ARRAY_AGG(w.{var_refs}) AS {var_refs},
              CAST(SUBSTR(CAST(y.{var_year} AS STRING), 1, 4) AS INT64) AS {var_year}
            FROM
              `{source_data}` AS w
            JOIN
              `{year_table}` y
            ON
              w.{source_id} = y.{source_id}
            WHERE
              w.{source_id} IN (
                SELECT DISTINCT {source_id}
                FROM `{source_data}`
                WHERE {var_refs} IN (SELECT id FROM initial_works)
              )
            GROUP BY w.{source_id}, CAST(SUBSTR(CAST(y.{var_year} AS STRING), 1, 4) AS INT64)
          )"""

      self.initial_works_template = initial_works_template.format(
          var_year=self.var_year,
          var_refs=self.var_refs,
          source_id=self.source_id,
          source_data=self.source_data,
          year_table=self.year_table,
          citation_filter=self.citation_filter)

      self.cit_works_template = cit_works_template.format(
          var_year=self.var_year,
          var_refs=self.var_refs,
          source_id=self.source_id,
          source_data=self.source_data,
          year_table=self.year_table)

    else:
      if self.aggregated:
        initial_works_template = """initial_works AS (
            SELECT
              {source_id} AS id,
              {var_refs},
              {var_year}
            FROM
              `{source_data}`
            WHERE
              {var_refs} IS NOT NULL
              AND ARRAY_LENGTH({var_refs}) > 0
              AND {source_id} IN (SELECT id FROM chunked_data)
              {citation_filter}
            GROUP BY {source_id}, {var_refs}, {var_year}
          )"""

        cit_works_template = """cit_works AS (
            SELECT
              w.{source_id} AS id,
              w.{var_refs},
              w.{var_year}
            FROM
              `{source_data}` w,
            UNNEST(w.{var_refs}) AS ref_id
            WHERE
              w.{var_refs} IS NOT NULL
              AND ARRAY_LENGTH(w.{var_refs}) > 0
              AND ref_id IN (SELECT id FROM initial_works)
            GROUP BY {source_id}, {var_refs}, {var_year}
          )"""
      else:
        initial_works_template = """initial_works AS (
            SELECT
              {source_id} AS id,
              ARRAY_AGG({var_refs}) AS {var_refs},
              {var_year}
            FROM
              `{source_data}`
            WHERE
              {var_refs} IS NOT NULL
              AND {source_id} IN (SELECT id FROM chunked_data)
              {citation_filter}
            GROUP BY {source_id}, {var_year}
          )"""

        cit_works_template = """cit_works AS (
            SELECT
              w.{source_id} AS id,
              ARRAY_AGG(w.{var_refs}) AS {var_refs},
              w.{var_year}
            FROM
              `{source_data}` AS w
            WHERE
              w.{source_id} IN (
                SELECT DISTINCT {source_id}
                FROM `{source_data}`
                WHERE {var_refs} IN (SELECT id FROM initial_works)
              )
            GROUP BY w.{source_id}, w.{var_year}
          )"""

      self.initial_works_template = initial_works_template.format(
          var_year=self.var_year,
          var_refs=self.var_refs,
          source_id=self.source_id,
          source_data=self.source_data,
          citation_filter=self.citation_filter)

      self.cit_works_template = cit_works_template.format(
          var_year=self.var_year,
          var_refs=self.var_refs,
          source_id=self.source_id,
          source_data=self.source_data)

    self.insert_query_template = """
    DECLARE Y INT64 DEFAULT {Y};  -- 0 for no time window restriction (past+future)

    INSERT INTO `{project}.{dataset}.{table_out}`

    WITH {data_to_search},

    numbered_data AS (
      SELECT
        id,
        ROW_NUMBER() OVER (ORDER BY id) AS row_num
      FROM
        data_to_search
    ),

    chunked_data AS (
      SELECT id
      FROM numbered_data
      WHERE row_num > {chunk_number} * 10000
        AND row_num <= ({chunk_number} + 1) * 10000
    ),

    {initial_works_template},
    {cit_works_template},

    all_data AS (
      SELECT
        wd1.id,
        wd1.{var_refs} AS ref,
        wd2.id AS cit,
        wd2.{var_refs} AS cit_ref,
        wd1.{var_year} AS fp_year,
        wd2.{var_year} AS cit_year
      FROM initial_works wd1
      INNER JOIN cit_works wd2
      ON wd1.id IN UNNEST(wd2.{var_refs})
      WHERE
        Y = 0
        OR (
          (wd2.{var_year} - wd1.{var_year}) >= 0
          AND (wd2.{var_year} - wd1.{var_year}) <= Y
        )
    ),

    di_nok_prep AS (
      SELECT
        id,
        cit,
        ref,
        cit_ref,
        (
          SELECT COUNT(1)
          FROM UNNEST(ref) AS r
          INNER JOIN UNNEST(IFNULL(cit_ref, [])) AS cr ON r = cr
        ) AS common_cit,
        ARRAY_LENGTH(ref) AS nb_ref
      FROM all_data
    ),

    DI_nok AS (
      SELECT
        id,
        nb_ref,
        COUNT(DISTINCT cit) AS nb_cit,
        SUM(CASE WHEN common_cit > 0 THEN 1 ELSE 0 END) AS J,
        SUM(CASE WHEN common_cit > 4 THEN 1 ELSE 0 END) AS J_5,
        SUM(CASE WHEN common_cit = 0 THEN 1 ELSE 0 END) AS I,
      FROM di_nok_prep
      GROUP BY id, nb_ref
    ),

    DI_nok_final AS (
      SELECT
        id,
        nb_ref,
        nb_cit,
        J,
        J_5,
        I,
        CASE
          WHEN (I + J) > 0 THEN (I - J) / (I + J)
          ELSE NULL
        END AS DI_nok1,
        CASE
          WHEN (I + J_5) > 0 THEN (I - J_5) / (I + J_5)
          ELSE NULL
        END AS DI_nok5,
        CASE
          WHEN nb_cit > 0 AND (I + J) > 0 THEN ((I - J) / (I + J) + 1) / 2
          ELSE NULL
        END AS dependence
      FROM DI_nok
    ),

    id_cit_list AS (
      SELECT
        id,
        ARRAY_AGG(cit) AS cit_list
      FROM all_data
      GROUP BY id
    ),

    breath_calc AS (
      SELECT
        main.id,
        (
          SELECT COUNT(1) > 0
          FROM UNNEST(IFNULL(main.cit_ref, [])) AS cr
          INNER JOIN UNNEST(agg.cit_list) AS cl ON cr = cl
        ) AS has_intersection
      FROM all_data AS main
      INNER JOIN id_cit_list AS agg ON main.id = agg.id
    ),

    Breath AS (
      SELECT
        id,
        AVG(IF(has_intersection, 1, 0)) AS Breath
      FROM breath_calc
      GROUP BY id
    ),

    all_disruption AS (
      SELECT
        COALESCE(d.id, b.id) AS id,
        d.nb_ref,
        d.nb_cit,
        d.J,
        d.J_5,
        d.I,
        d.DI_nok1,
        d.DI_nok5,
        d.dependence,
        b.Breath
      FROM DI_nok_final AS d
      FULL OUTER JOIN Breath AS b ON d.id = b.id
    )

    SELECT *
    FROM all_disruption
    """


  def get_nb_chunks(self):


      # First, get the total count
      count_query = """
      SELECT COUNT(DISTINCT {var_id}) as total_records
      FROM `{project}.{dataset}.{table_id}`
      """.format(project = self.project,
                dataset = self.dataset,
                table_id = self.table_id,
                var_id = self.var_id)

      result = self.client.query(count_query).result()
      self.total_records = list(result)[0].total_records
      self.total_chunks = (self.total_records + 9999) // 10000  # Ceiling division

      print(f"Total records: {self.total_records}")
      print(f"Total chunks to process: {self.total_chunks}")


  def create_table(self):
    # Create the target table if it doesn't exist
    create_table_query = """
    CREATE TABLE IF NOT EXISTS `{project}.{dataset}.{table_out}` (
      id STRING,
      nb_ref INT64,
      nb_cit INT64,
      J INT64,
      J_5 INT64,
      I INT64,
      DI_nok1 FLOAT64,
      DI_nok5 FLOAT64,
      dependence FLOAT64,
      Breath FLOAT64
    )
    """.format(project = self.project,
                dataset = self.dataset,
                table_out = self.table_out)
    self.client.query(create_table_query).result()
    print("Target table created/verified")

  def compute_all_chunks(self):
    for chunk_num in tqdm.tqdm(range(self.total_chunks)): #

      # Get row count before insertion
      count_query = """
      SELECT COUNT(*) as row_count
      FROM `{project}.{dataset}.{table_out}`
      """.format(project=self.project,
                  dataset=self.dataset,
                  table_out=self.table_out)

      before_result = self.client.query(count_query).result()
      rows_before = list(before_result)[0].row_count

      query = self.insert_query_template.format(
                                          Y=self.Y,
                                          chunk_number=chunk_num,
                                          project=self.project,
                                          dataset=self.dataset,
                                          data_to_search = self.data_to_search,
                                          table_out=self.table_out,
                                          var_id=self.var_id,
                                          var_refs=self.var_refs,
                                          var_year=self.var_year,
                                          source_data=self.source_data,
                                          initial_works_template = self.initial_works_template,
                                          cit_works_template = self.cit_works_template,)

      try:
        job = self.client.query(query)
        result = job.result()

        after_result = self.client.query(count_query).result()
        rows_after = list(after_result)[0].row_count
        rows_inserted = rows_after - rows_before

        print(f"Chunk {chunk_num + 1} completed successfully. Rows inserted: {rows_inserted}")
        time.sleep(2)

      except Exception as e:
        print(f"Error processing chunk {chunk_num + 1}: {str(e)}")
        continue

  def compute_metrics(self):
    self.get_nb_chunks()
    self.create_table()
    self.compute_all_chunks()