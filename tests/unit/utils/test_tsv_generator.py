from src.utils.tsv_generator import create_tsv_from_config

# Use default config
tsv_path = create_tsv_from_config("alma_lgtbq_files_config.json")

# # Override set ID or environment
# tsv_path = create_tsv_from_config("alma_tsv_config.json", 
#                                  set_id_override="different_set",
#                                  environment_override="PRODUCTION")