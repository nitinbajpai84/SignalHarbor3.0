import { copy } from "../copy";
import { useTheme, type ThemeChoice } from "../theme";

const CHOICES: { value: ThemeChoice; label: string }[] = [
  { value: "light", label: copy.theme.light },
  { value: "dark", label: copy.theme.dark },
  { value: "system", label: copy.theme.system },
];

/** Three plain choices in one radio group: arrow keys move between them, focus is drawn on the label. */
export default function ThemeControl() {
  const { choice, setChoice } = useTheme();
  return (
    <fieldset className="theme-control">
      <legend className="visually-hidden">{copy.theme.legend}</legend>
      {CHOICES.map((c) => (
        <label key={c.value} className="theme-choice">
          <input
            type="radio"
            name="theme"
            className="visually-hidden"
            value={c.value}
            checked={choice === c.value}
            onChange={() => setChoice(c.value)}
          />
          <span>{c.label}</span>
        </label>
      ))}
    </fieldset>
  );
}
