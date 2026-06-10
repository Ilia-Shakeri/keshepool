import os

def generate_tree(startpath, exclude_dirs, exclude_files, exclude_exts):
    """
    Generates a visual tree structure of the project.
    """
    tree_str = "PROJECT STRUCTURE:\n"
    tree_str += f"{os.path.basename(os.path.abspath(startpath))}/\n"
    
    for root, dirs, files in os.walk(startpath):
        # Filter directories in-place to prevent os.walk from entering them
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * level
        sub_indent = ' ' * 4 * (level + 1)
        
        if level > 0:
            tree_str += f"{indent}{os.path.basename(root)}/\n"
        
        for f in sorted(files):
            file_ext = os.path.splitext(f)[1].lower()
            if f not in exclude_files and file_ext not in exclude_exts:
                tree_str += f"{sub_indent}{f}\n"
    return tree_str

def merge_project_files(output_filename="full_ZoodSub_project_code.txt"):
    # Added 'fonts' to prevent traversing into the font directories
    EXCLUDE_DIRS = {
        'node_modules', '.git', '.idea', '__pycache__', 
        'venv', 'env', '.vscode', 'dist', 'build', '.terraform', 
        'vendor', '.venv', '.next', 'public', 'static', '.turbo',
        'fonts' 
    }
    
    # Added font extensions and web link extensions to keep the core logic clean
    EXCLUDE_EXTENSIONS = {
        '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg',
        '.pyc', '.exe', '.dll', '.so', '.sqlite', '.db', 
        '.lock', '.pdf', '.docx', '.map', '.mjs', '.css', '.md',
        '.ttf', '.woff', '.woff2', '.eot', '.otf', '.url'
    }

    # Added the specific 'read me!.txt' found in your fonts folder to the exclusion list
    EXCLUDE_FILES = {
        output_filename, 
        'package-lock.json',
        'yarn.lock',
        'code_dumper.py',
        '.DS_Store',
        'components.json',
        'tsconfig.json',
        'next-env.d.ts',
        'read me!.txt'
    }

    print(f"Generating project tree and merging files into {output_filename}...")

    with open(output_filename, 'w', encoding='utf-8') as outfile:
        project_tree = generate_tree(".", EXCLUDE_DIRS, EXCLUDE_FILES, EXCLUDE_EXTENSIONS)
        outfile.write(project_tree)
        outfile.write(f"\n{'#'*60}\n")
        outfile.write(f"{'#'*15} FILE CONTENTS START BELOW {'#'*15}\n")
        outfile.write(f"{'#'*60}\n\n")

        for root, dirs, files in os.walk("."):
            # Ensure directories are filtered during the file dump phase as well
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            for file in sorted(files):
                file_ext = os.path.splitext(file)[1].lower()
                
                # Skip excluded files and extensions
                if (file in EXCLUDE_FILES or file_ext in EXCLUDE_EXTENSIONS):
                    continue

                file_path = os.path.join(root, file)

                try:
                    outfile.write(f"\n{'='*50}\n")
                    outfile.write(f"FILE: {file_path}\n")
                    outfile.write(f"{'='*50}\n\n")

                    with open(file_path, 'r', encoding='utf-8') as infile:
                        outfile.write(infile.read())
                        outfile.write("\n")
                    
                    print(f"Added: {file_path}")

                except Exception as e:
                    print(f"Skipping {file_path}: {e}")

    print(f"\nDone! Clean project overview and code are in {output_filename}")

if __name__ == "__main__":
    merge_project_files()