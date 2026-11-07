/**
 * markdownPasteHelper.js
 * 
 * Handles rich copy-paste into Markdown textareas:
 * 1. Converts rich HTML (from Microsoft Word, PDFs, Google Docs, Web) into clean Markdown.
 * 2. Preserves bold formatting (**text**), headings (###), bullet points, and tables.
 * 3. Preserves mathematical symbols, Greek letters, subscripts (sub), superscripts (sup), and formulas.
 * 4. Normalizes maritime engineering and IMO regulatory notation (e.g., ϕf -> ϕ<sub>f</sub>, lw1 -> l<sub>w1</sub>, CO2 -> CO<sub>2</sub>, .1/.2 lists).
 * 5. Intercepts pasted image files/screenshots and converts them into inline Markdown images:
 *    ![Figure Diagram](data:image/png;base64,...)
 */

/**
 * Normalizes Greek and mathematical symbols copied from Word/PDFs.
 */
export const normalizeMathSymbols = (text) => {
  if (!text) return "";
  let res = text
    // Replace Word curly quotes and special apostrophes
    .replace(/[\u2018\u2019\u201A\u201B]/g, "'")
    .replace(/[\u201C\u201D\u201E\u201F]/g, '"')
    // Standardize Greek phi symbols: U+03D5 (ϕ) and U+03C6 (φ) to uniform ϕ
    .replace(/\u03C6/g, "ϕ")
    // Non-breaking hyphens, en-dashes, em-dashes, and math minus
    .replace(/\u2011/g, "-")
    .replace(/\u2012|\u2013/g, "-")
    .replace(/\u2014/g, " — ")
    .replace(/\u2212/g, "-")
    // Replace non-breaking spaces
    .replace(/\u00A0/g, " ")
    // Replace zero-width spaces and soft hyphens
    .replace(/[\u200B\u200C\u200D\uFEFF\u00AD]/g, "")
    // Standardize bullet points
    .replace(/[•\u2022\u25E6\u2023\u2043\u25AA\u25AB\u2219]/g, "•");

  // Autodetect plain-text maritime formulas and parameters when pasted without HTML tags
  // Ensures subscripts and superscripts are restored accurately from raw text / PDF extraction
  res = res
    // Angle of down-flooding (ϕf, ϕ_f -> ϕ<sub>f</sub>)
    .replace(/(?<=^|[^a-zA-Z0-9])(?:ϕ|φ)_?f(?![a-zA-Z0-9])/g, "ϕ<sub>f</sub>")
    // Angle of equilibrium (ϕ0, ϕ_0 -> ϕ<sub>0</sub>)
    .replace(/(?<=^|[^a-zA-Z0-9])(?:ϕ|φ)_?0(?![a-zA-Z0-9])/g, "ϕ<sub>0</sub>")
    // Angle of roll to windward (ϕ1, ϕ_1 -> ϕ<sub>1</sub>)
    .replace(/(?<=^|[^a-zA-Z0-9])(?:ϕ|φ)_?1(?![a-zA-Z0-9])/g, "ϕ<sub>1</sub>")
    // Angle of roll (ϕ2, ϕ_2 -> ϕ<sub>2</sub>)
    .replace(/(?<=^|[^a-zA-Z0-9])(?:ϕ|φ)_?2(?![a-zA-Z0-9])/g, "ϕ<sub>2</sub>")
    // Wind heeling levers (lw1, lw2, l_w1, l_w2 -> l<sub>w1</sub>, l<sub>w2</sub>)
    .replace(/\b(lw1|l_w1)\b/g, "l<sub>w1</sub>")
    .replace(/\b(lw2|l_w2)\b/g, "l<sub>w2</sub>")
    // Metacentric height (GMo, GM0, GM_0 -> GM<sub>0</sub>)
    .replace(/\b(GMo|GM0|GM_0)\b/g, "GM<sub>0</sub>")
    // Down-flooding theta (θf, θ_f -> θ<sub>f</sub>)
    .replace(/(?<=^|[^a-zA-Z0-9])θ_?f(?![a-zA-Z0-9])/g, "θ<sub>f</sub>")
    // Maritime emissions and gases (CO2, SOx, NOx, H2S, CH4, O2, N2)
    .replace(/\bCO2\b/g, "CO<sub>2</sub>")
    .replace(/\bSOx\b/g, "SO<sub>x</sub>")
    .replace(/\bNOx\b/g, "NO<sub>x</sub>")
    .replace(/\bH2S\b/g, "H<sub>2</sub>S")
    .replace(/\bCH4\b/g, "CH<sub>4</sub>")
    .replace(/\bO2\b/g, "O<sub>2</sub>")
    .replace(/\bN2\b/g, "N<sub>2</sub>")
    // Standard units: m3, m2, cm3, cm2
    .replace(/\b(\d+)\s*m3\b/g, "$1 m<sup>3</sup>")
    .replace(/\b(\d+)\s*m2\b/g, "$1 m<sup>2</sup>");

  return res;
};

/**
 * Converts a DOM node into Markdown string recursively.
 */
function nodeToMarkdown(node) {
  if (!node) return "";

  // Text node
  if (node.nodeType === Node.TEXT_NODE) {
    return node.textContent;
  }

  // Not an element node
  if (node.nodeType !== Node.ELEMENT_NODE) {
    return "";
  }

  const tag = node.tagName.toLowerCase();

  // Ignore scripts, styles, XML metadata, and Word comments
  if (
    tag === "script" ||
    tag === "style" ||
    tag === "xml" ||
    tag === "meta" ||
    tag === "link"
  ) {
    return "";
  }

  // Check inline styles for bold, italic, and subscripts/superscripts (common in Word HTML)
  const style = node.getAttribute("style") || "";
  const isBoldStyle =
    /font-weight\s*:\s*(bold|[7-9]00)/i.test(style) ||
    tag === "b" ||
    tag === "strong";
  const isItalicStyle =
    /font-style\s*:\s*italic/i.test(style) ||
    tag === "i" ||
    tag === "em";
  const isSubStyle =
    tag === "sub" ||
    /vertical-align\s*:\s*sub/i.test(style) ||
    /mso-char-type\s*:\s*subscript/i.test(style) ||
    /mso-text-raise\s*:\s*-\d+/i.test(style);
  const isSuperStyle =
    tag === "sup" ||
    /vertical-align\s*:\s*super/i.test(style) ||
    /mso-char-type\s*:\s*superscript/i.test(style) ||
    /mso-text-raise\s*:\s*\+?\d+/i.test(style);

  // Recursively process children
  let childrenText = "";
  for (let child of node.childNodes) {
    childrenText += nodeToMarkdown(child);
  }

  // Formatting based on HTML tag
  switch (tag) {
    case "h1":
      return `\n\n# ${childrenText.trim()}\n\n`;
    case "h2":
      return `\n\n## ${childrenText.trim()}\n\n`;
    case "h3":
      return `\n\n### ${childrenText.trim()}\n\n`;
    case "h4":
    case "h5":
    case "h6":
      return `\n\n#### ${childrenText.trim()}\n\n`;

    case "p":
    case "div": {
      const trimmed = childrenText.trim();
      if (!trimmed) return "";
      // Check if the entire paragraph was bolded (often used as heading in Word)
      if (isBoldStyle && !trimmed.startsWith("**") && !trimmed.endsWith("**")) {
        return `\n\n**${trimmed}**\n\n`;
      }
      return `\n\n${trimmed}\n\n`;
    }

    case "b":
    case "strong": {
      const trimmed = childrenText.trim();
      if (!trimmed) return "";
      return `**${trimmed}**`;
    }

    case "i":
    case "em": {
      const trimmed = childrenText.trim();
      if (!trimmed) return "";
      return `*${trimmed}*`;
    }

    case "sub": {
      const trimmed = childrenText.trim();
      if (!trimmed) return "";
      return `<sub>${trimmed}</sub>`;
    }

    case "sup": {
      const trimmed = childrenText.trim();
      if (!trimmed) return "";
      return `<sup>${trimmed}</sup>`;
    }

    case "del":
    case "s":
    case "strike": {
      const trimmed = childrenText.trim();
      if (!trimmed) return "";
      return `~~${trimmed}~~`;
    }

    case "u":
    case "ins": {
      return childrenText;
    }

    case "code":
      return `\`${childrenText}\``;

    case "pre":
      return `\n\n\`\`\`\n${childrenText.trim()}\n\`\`\`\n\n`;

    case "blockquote":
      return `\n\n> ${childrenText.trim().replace(/\n/g, "\n> ")}\n\n`;

    case "ul":
      return `\n${childrenText}\n`;

    case "ol":
      return `\n${childrenText}\n`;

    case "li": {
      const trimmed = childrenText.trim();
      if (!trimmed) return "";
      const isOrdered = node.parentElement && node.parentElement.tagName.toLowerCase() === "ol";
      if (isOrdered) {
        // Find index among sibling li elements
        let idx = 1;
        let prev = node.previousElementSibling;
        while (prev) {
          if (prev.tagName.toLowerCase() === "li") idx++;
          prev = prev.previousElementSibling;
        }
        return `${idx}. ${trimmed}\n`;
      }
      return `- ${trimmed}\n`;
    }

    case "br":
      return "\n";

    case "img": {
      const src = node.getAttribute("src") || "";
      const alt = node.getAttribute("alt") || "Diagram";
      if (src) {
        return `\n\n![${alt}](${src})\n\n`;
      }
      return "";
    }

    case "table": {
      // Process table into Markdown format
      return formatTableToMarkdown(node);
    }

    default: {
      let result = childrenText;
      if (isSubStyle && !result.startsWith("<sub>") && !result.endsWith("</sub>")) {
        const trimmed = result.trim();
        if (trimmed) result = `<sub>${trimmed}</sub>`;
      } else if (isSuperStyle && !result.startsWith("<sup>") && !result.endsWith("</sup>")) {
        const trimmed = result.trim();
        if (trimmed) result = `<sup>${trimmed}</sup>`;
      }

      if (isBoldStyle) {
        const trimmed = result.trim();
        if (trimmed && !trimmed.startsWith("**") && !trimmed.endsWith("**")) {
          result = `**${trimmed}**`;
        }
      }
      if (isItalicStyle) {
        const trimmed = result.trim();
        if (trimmed && !trimmed.startsWith("*") && !trimmed.endsWith("*")) {
          result = `*${trimmed}*`;
        }
      }
      return result;
    }
  }
}

/**
 * Converts a table element into clean GFM Markdown table.
 */
function formatTableToMarkdown(tableNode) {
  const rows = tableNode.querySelectorAll("tr");
  if (!rows || rows.length === 0) return "";

  let md = "\n\n";
  let colCount = 0;

  rows.forEach((row, rowIdx) => {
    const cells = row.querySelectorAll("th, td");
    if (cells.length === 0) return;

    if (rowIdx === 0) {
      colCount = cells.length;
    }

    const cellTexts = Array.from(cells).map((c) =>
      nodeToMarkdown(c)
        .replace(/\r?\n+/g, "<br>")
        .replace(/\|/g, "\\|")
        .trim()
    );

    md += `| ${cellTexts.join(" | ")} |\n`;

    if (rowIdx === 0) {
      md += `| ${Array(colCount).fill("---").join(" | ")} |\n`;
    }
  });

  return md + "\n";
}

/**
 * Converts rich HTML from the clipboard into Markdown.
 */
export const htmlToMarkdown = (htmlString) => {
  if (!htmlString || typeof htmlString !== "string") return "";

  try {
    // Clean Word HTML comments
    const cleanedHtml = htmlString
      .replace(/<!--[\s\S]*?-->/g, "")
      .replace(/<!\[[\s\S]*?\]>/g, "");

    const parser = new DOMParser();
    const doc = parser.parseFromString(cleanedHtml, "text/html");
    const body = doc.body;

    let md = nodeToMarkdown(body);

    // Clean up excessive blank lines
    md = md.replace(/\n{3,}/g, "\n\n").trim();

    return normalizeMathSymbols(md);
  } catch (err) {
    console.warn("Failed to parse HTML to Markdown:", err);
    return "";
  }
};

/**
 * Formats plain text if no HTML was available (e.g. from notepad or raw PDF copy).
 * Detects headers, bullet points, checklists, and IMO-style dot-numbered lists.
 */
export const formatPlainTextWithBullets = (text) => {
  if (!text) return "";
  let formatted = normalizeMathSymbols(text);

  // Convert checkmark bullets to Markdown checklists
  formatted = formatted.replace(/^[ \t]*[✓✔☑][ \t]+/gm, "- [x] ");
  formatted = formatted.replace(/^[ \t]*[✗✘☒][ \t]+/gm, "- [ ] ");

  // Convert standard bullet symbols to Markdown bullets
  formatted = formatted.replace(/^[ \t]*[•\⁃\◦\▪\▫\–\‣\■][ \t]+/gm, "- ");

  // Format IMO-style dot-numbered items (e.g., ".1 cargo ships;", ".2 passenger ships;")
  formatted = formatted.replace(/(?:^|\n)[ \t]*\.([0-9IVXLCDM]+|[a-z])\s+(.+)$/gim, "\n- **.$1** $2");

  // Ensure bold headers on lines ending with colon or bullet headers e.g. "• Dynamic stability:" -> "- **Dynamic stability:**"
  formatted = formatted.replace(
    /^[ \t]*-\s*([A-Za-z0-9\s,/\-()]{3,60}:)/gm,
    "- **$1**"
  );

  return formatted;
};

/**
 * Inserts text at the current cursor position of a textarea or wraps selection.
 */
export const insertAtCursor = (textarea, textToInsert, currentText, setText) => {
  if (!textarea) {
    setText((prev) => (prev ? prev + "\n\n" + textToInsert : textToInsert));
    return;
  }

  const start = textarea.selectionStart || 0;
  const end = textarea.selectionEnd || 0;
  const before = currentText.substring(0, start);
  const after = currentText.substring(end);

  const newText = before + textToInsert + after;
  setText(newText);

  // Restore cursor position right after the inserted text
  setTimeout(() => {
    textarea.focus();
    const newPos = start + textToInsert.length;
    textarea.setSelectionRange(newPos, newPos);
  }, 10);
};

/**
 * Wraps the current selection with prefix and suffix (e.g. <sub>selection</sub>),
 * or inserts prefix+suffix with cursor placed between them if nothing is selected.
 */
export const wrapSelectionOrInsert = (textarea, prefix, suffix, currentText, setText) => {
  if (!textarea) {
    setText((prev) => (prev ? `${prev} ${prefix}${suffix}` : `${prefix}${suffix}`));
    return;
  }

  const start = textarea.selectionStart || 0;
  const end = textarea.selectionEnd || 0;
  const selectedText = currentText.substring(start, end);
  const before = currentText.substring(0, start);
  const after = currentText.substring(end);

  if (selectedText.length > 0) {
    const wrapped = `${prefix}${selectedText}${suffix}`;
    const newText = before + wrapped + after;
    setText(newText);
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start, start + wrapped.length);
    }, 10);
  } else {
    const newText = before + prefix + suffix + after;
    setText(newText);
    setTimeout(() => {
      textarea.focus();
      const cursorInside = start + prefix.length;
      textarea.setSelectionRange(cursorInside, cursorInside);
    }, 10);
  }
};

/**
 * Reads an image file as a Base64 Data URL.
 */
export const readImageAsBase64 = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => resolve(e.target.result);
    reader.onerror = (err) => reject(err);
    reader.readAsDataURL(file);
  });
};

/**
 * Main onPaste event handler for Markdown textareas.
 * Handles both rich formatted text and clipboard images.
 */
export const handleSmartPaste = async (e, currentText, setText, textareaRef) => {
  const clipboardData = e.clipboardData || window.clipboardData;
  if (!clipboardData) return;

  const textarea = textareaRef?.current || e.target;

  // 1. Check for Image Files in clipboard (e.g. screenshots, copied diagrams)
  const items = clipboardData.items;
  let imageFile = null;

  if (items) {
    for (let i = 0; i < items.length; i++) {
      if (items[i].type && items[i].type.startsWith("image/")) {
        imageFile = items[i].getAsFile();
        break;
      }
    }
  }

  if (!imageFile && clipboardData.files && clipboardData.files.length > 0) {
    for (let i = 0; i < clipboardData.files.length; i++) {
      if (clipboardData.files[i].type && clipboardData.files[i].type.startsWith("image/")) {
        imageFile = clipboardData.files[i];
        break;
      }
    }
  }

  // If an image was pasted, convert to Base64 Markdown image and insert!
  if (imageFile) {
    e.preventDefault();
    try {
      const base64Data = await readImageAsBase64(imageFile);
      const diagramName = imageFile.name ? imageFile.name.replace(/\.[^/.]+$/, "") : "Diagram";
      const imageMarkdown = `\n\n![${diagramName}](${base64Data})\n\n`;
      insertAtCursor(textarea, imageMarkdown, currentText, setText);
      return;
    } catch (err) {
      console.error("Failed to read pasted image:", err);
    }
  }

  // 2. Check for Rich HTML from Word / PDF / Web
  const html = clipboardData.getData("text/html");
  if (html && html.trim().length > 0) {
    const markdown = htmlToMarkdown(html);
    if (markdown && markdown.length > 0) {
      e.preventDefault();
      insertAtCursor(textarea, markdown, currentText, setText);
      return;
    }
  }

  // 3. Fallback: Plain text with symbol normalization and bullet support
  const plainText = clipboardData.getData("text/plain");
  if (plainText) {
    const formatted = formatPlainTextWithBullets(plainText);
    if (formatted !== plainText) {
      e.preventDefault();
      insertAtCursor(textarea, formatted, currentText, setText);
      return;
    }
  }
};
