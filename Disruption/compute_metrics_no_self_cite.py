import re
from Disruption.disruption_without_self_citations import Disruption_no_self_cite

# true_match - OA
for year in [0, 5]:
    Disruption_no_self_cite(
        project='long-sonar-470413-q7',
        dataset='PPP_project',
        table_id='true_match',
        table_out='true_match_disruption_Y' + str(year) + '_no_selfcite',
        var_id='work_id',
        Y=year,
        var_refs='referenced_works',
        var_year='publication_year',
        source_data='nber-i3.openalex.works_241125',
        source_id='id',
        remove_self_cite_refs=True,
        remove_self_cite_cits=True,
    ).compute_metrics()

# true_match - patents
for year in [0, 5]:
    for cat in ['', 'cited by examiner', 'cited by applicant']:
        cat_type = '_' + re.sub(' ', '_', cat) if cat else ''
        table_out = 'true_match_disruption_patent' + cat_type + '_Y' + str(year) + '_no_selfcite'
        Disruption_no_self_cite(
            project='long-sonar-470413-q7',
            dataset='PPP_project',
            table_id='true_match',
            table_out=table_out,
            var_id='patent_id_us',
            Y=year,
            var_refs='citation_patent_id',
            var_year='patent_date',
            source_data='nber-i3.patentsview_granted.g_us_patent_citation_20250317',
            source_id='patent_id',
            aggregated_ref=False,
            patent=True,
            year_table='nber-i3.patentsview_granted.g_patent_20250909',
            citation_category=cat,
            remove_self_cite_refs=True,
            remove_self_cite_cits=True,
            inventor_table='nber-i3.patentsview_granted.g_inventor_disambiguated_20250317',
        ).compute_metrics()

# MM_PPP - OA
for year in [0, 5]:
    Disruption_no_self_cite(
        project='long-sonar-470413-q7',
        dataset='PPP_project',
        table_id='MM_PPP',
        table_out='MM_PPP_disruption_Y' + str(year) + '_no_selfcite',
        var_id='paperid',
        Y=year,
        var_refs='referenced_works',
        var_year='publication_year',
        source_data='nber-i3.openalex.works_241125',
        source_id='id',
        to_concat_before='https://openalex.org/',
        remove_self_cite_refs=True,
        remove_self_cite_cits=True,
    ).compute_metrics()

# MM_PPP - patents
for year in [0, 5]:
    for cat in ['', 'cited by examiner', 'cited by applicant']:
        cat_type = '_' + re.sub(' ', '_', cat) if cat else ''
        table_out = 'MM_PPP_disruption_patent' + cat_type + '_Y' + str(year) + '_no_selfcite'
        Disruption_no_self_cite(
            project='long-sonar-470413-q7',
            dataset='PPP_project',
            table_id='MM_PPP',
            table_out=table_out,
            var_id='patent',
            Y=year,
            var_refs='citation_patent_id',
            var_year='patent_date',
            source_data='nber-i3.patentsview_granted.g_us_patent_citation_20250317',
            source_id='patent_id',
            aggregated_ref=False,
            patent=True,
            year_table='nber-i3.patentsview_granted.g_patent_20250909',
            citation_category=cat,
            remove_self_cite_refs=True,
            remove_self_cite_cits=True,
            inventor_table='nber-i3.patentsview_granted.g_inventor_disambiguated_20250317',
        ).compute_metrics()
