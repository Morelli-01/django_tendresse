# Bolla Drawer

This program is a Java-based utility for creating and managing shipping documents, referred to as "Bollas." It takes a JSON input describing the Bolla's details, generates a PDF representation of it, and saves it to the filesystem.

## Features

- **PDF Generation:** Creates a PDF of a Bolla from a JSON input.
- **Customizable:** The generated PDF's content is determined by the JSON input.

## How to Use

### Prerequisites

- Java 18 or higher
- Maven

### Building the Project

To build the project, run the following command from the project's root directory:

```bash
mvn clean install
```

This will compile the project and create a JAR file in the `target` directory.

### Running the Program

The program is executed from the command line. It expects at least one argument: a JSON string representing the Bolla to be created. It can also take two optional arguments: the output path for the generated PDF, and the path to the static files.

```bash
java -jar target/BollaDrawer-1.0-SNAPSHOT.jar '<json_string>' [output_path] [static_files_path]
```

- `<json_string>`: A JSON string representing the Bolla object.
- `[output_path]` (optional): The path where the generated PDF will be saved. If not provided, the PDF will be saved in a `Bolle` directory in the project's root.
- `[static_files_path]` (optional): The path to the static files (e.g., images). If not provided, the program will look for a `images` directory in the project's root.

### JSON Input Format

The JSON input must represent a `Bolla` object. Here are two examples of the JSON structure:

**Example 1: Same Address**

```json
{
  "data": "27/02/2023",
  "descrizioni": [
    "Filato Composizioni Diverse"
  ],
  "qta": [
    "10"
  ],
  "um": [
    "Kg"
  ],
  "note": [
    "---"
  ],
  "lavorazione": "Taglio",
  "respSpedizione": "mittente",
  "dataTrasp": "27/02/2023",
  "aspetto": "visibile",
  "dst": {
    "usr": "Nicola Morelli",
    "riga1": "Via Giacomo Puccini 22",
    "riga2": "",
    "citta": "Carpi",
    "prov": "MO",
    "cap": "41012",
    "paese": "Italia"
  },
  "sameAddress": true,
  "dst2": [],
  "number": "1",
  "year": "2023"
}
```

**Example 2: Different Address**

```json
{
  "data": "27/02/2023",
  "descrizioni": [
    "Filato Composizioni Diverse"
  ],
  "qta": [
    "10"
  ],
  "um": [
    "Kg"
  ],
  "note": [
    "---"
  ],
  "lavorazione": "Taglio",
  "respSpedizione": "mittente",
  "dataTrasp": "27/02/2023",
  "aspetto": "visibile",
  "dst": {
    "usr": "Nicola Morelli",
    "riga1": "Via Giacomo Puccini 22",
    "riga2": "",
    "citta": "Carpi",
    "prov": "MO",
    "cap": "41012",
    "paese": "Italia"
  },
  "sameAddress": false,
  "dst2": ["Mario Rossi","Via Verdi 10","Modena", "41121", "Italia" ],
  "number": "1",
  "year": "2023"
}
```

## Project Structure

- **`publicDrawer.java`**: The main class that handles the program's execution.
- **`Bolla.java`**: A data class representing a Bolla.
- **`drawBollaDefault.java`**: A utility class for generating the PDF document using Apache PDFBox.
- **`pom.xml`**: The Maven project configuration file.
- **`images/`**: A directory containing images used in the generated PDF.
- **`Bolle/`**: The directory where the generated PDFs are saved.

### Command Example

**Example 1: Same Address**

```bash
java -jar target/BollaDrawer-1.0-SNAPSHOT.jar '{"data":"27/02/2023","descrizioni":["Filato Composizioni Diverse"],"qta":["10"],"um":["Kg"],"note":["---"],"lavorazione":"Taglio","respSpedizione":"mittente","dataTrasp":"27/02/2023","aspetto":"visibile","dst":{"usr":"Nicola Morelli","riga1":"Via Giacomo Puccini 22","riga2":"","citta":"Carpi","prov":"MO","cap":"41012","paese":"Italia"},"sameAddress":true,"dst2":[],"number":"1","year":"2023"}'
```

**Example 2: Different Address**

```bash
java -jar target/BollaDrawer-1.0-SNAPSHOT.jar '{"data":"27/02/2023","descrizioni":["Filato Composizioni Diverse"],"qta":["10"],"um":["Kg"],"note":["---"],"lavorazione":"Taglio","respSpedizione":"mittente","dataTrasp":"27/02/2023","aspetto":"visibile","dst":{"usr":"Nicola Morelli","riga1":"Via Giacomo Puccini 22","riga2":"","citta":"Carpi","prov":"MO","cap":"41012","paese":"Italia"},"sameAddress":false,"dst2":["Mario Rossi","Via Verdi 10","Modena", "41121", "Italia"],"number":"1","year":"2023"}'
```

The `dst2` field is used to specify a different destination for the goods. If `sameAddress` is `false`, the `dst2` field will be used as the destination address. Otherwise, the `dst` field will be used. In the first example, `sameAddress` is `true`, so the `dst` field will be used. In the second example, `sameAddress` is `false`, so the `dst2` field will be used.
