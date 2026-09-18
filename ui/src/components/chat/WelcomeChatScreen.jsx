import React from "react";
import DolphinIconB from "../../assets/images/dolphin_b.png";
import DolphinIconW from "../../assets/images/dolphin_w.png";
import ShipIconB from "../../assets/images/ship.png";
import ShipIconW from "../../assets/images/ship_w.png";
import { useThemeMode } from "../../context/ThemeModeContext";

const WelcomeChatScreen = () => {
  const { mode } = useThemeMode();

  return (
    <div className="flex-1 flex items-center justify-center p-4 select-none">
      <div className="w-full max-w-[420px] bg-bg-paper rounded-2xl sm:rounded-3xl px-5 sm:px-7 py-5 sm:py-6 text-center flex flex-col items-center gap-2.5 sm:gap-3 border border-primary/25 dark:border-primary/35 shadow-md hover:shadow-lg hover:border-primary/40 transition-all duration-200">
        {/* Icons */}
        <div className="flex items-center justify-center gap-2.5">
          <img
            src={mode === "dark" ? DolphinIconW : DolphinIconB}
            alt="Dolphin"
            className="w-9 h-9 sm:w-10 sm:h-10 object-contain drop-shadow-xs"
          />
          <img
            src={mode === "dark" ? ShipIconW : ShipIconB}
            alt="Ship"
            className="w-6 h-6 sm:w-7 sm:h-7 object-contain drop-shadow-xs"
          />
        </div>

        {/* Title */}
        <div className="flex items-center justify-center gap-1.5 text-base sm:text-lg font-bold tracking-tight">
          <span className="text-text-primary">Dolphin</span>
          <span className="text-text-secondary opacity-60 font-light">|</span>
          <span className="text-primary">AI</span>
        </div>

        {/* Subtitle with gradient */}
        <h2 className="text-base sm:text-lg font-medium text-text-primary m-0">
          How can I{" "}
          <span className="bg-linear-to-r from-primary to-sky-400 bg-clip-text text-transparent font-semibold">
            help
          </span>{" "}
          you today?
        </h2>

        {/* Description - content unchanged */}
        <p className="text-xs sm:text-[13px] font-normal text-text-secondary leading-relaxed m-0 max-w-sm">
          You can ask me anything. I can provide summaries, key takeaways and
          knowledge checks, as well as help you locate specific videos from our
          library and recommend training courses to enhance your skills.
        </p>
      </div>
    </div>
  );
};

export default WelcomeChatScreen;
