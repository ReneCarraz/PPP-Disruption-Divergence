import re
from Disruption.disruption_with_self_citations import Disruption

# random_sample_OA
for year in [0, 5]:
    Disruption(
        project='healthy-highway-455915-t4',
        dataset='PPP_project',
        table_id='random_sample_OA',
        table_out='random_sample_OA_disruption_Y' + str(year),
        var_id='control_work_id',
        Y=year,
        var_refs='referenced_works',
        var_year='publication_year',
        source_data='nber-i3.openalex.works_241125',
        source_id='id',
        to_concat_before='',
    ).compute_metrics()

# random_sample_patents
for year in [0, 5]:
    for cat in ['', 'cited by examiner', 'cited by applicant']:
        cat_type = '_' + re.sub(' ', '_', cat) if cat else ''
        table_out = 'random_sample_patents_disruption_' + cat_type + '_y' + str(year)
        print(table_out)
        Disruption(
            project='healthy-highway-455915-t4',
            dataset='PPP_project',
            table_id='random_sample_patents',
            table_out=table_out,
            var_id='control_patent_id',
            Y=year,
            var_refs='citation_patent_id',
            var_year='patent_date',
            source_data='nber-i3.patentsview_granted.g_us_patent_citation_20250317',
            source_id='patent_id',
            aggregated_ref=False,
            patent=True,
            year_table='nber-i3.patentsview_granted.g_patent_20250909',
            citation_category=cat,
        ).compute_metrics()
