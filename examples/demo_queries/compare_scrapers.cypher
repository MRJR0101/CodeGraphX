// Compare call trees: MainScraper vs UltimateScraper
// Find functions with the same name that exist in both projects
MATCH (f1:Function {project: "MainScraper"})
MATCH (f2:Function {project: "UltimateScraper"})
WHERE f1.name = f2.name
RETURN f1.name AS shared_function,
       f1.path AS main_path, f1.start_line AS main_line,
       f2.path AS ultimate_path, f2.start_line AS ultimate_line;
