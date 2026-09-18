import React, { useState, useEffect } from "react";

const MainLayout = ({ header, leftPanel, contentPanel }) => {
  // Mobile / tablet detection matching 900px breakpoint
  const [isDesktop, setIsDesktop] = useState(
    typeof window !== "undefined" ? window.innerWidth >= 900 : true
  );

  useEffect(() => {
    const handleResize = () => {
      setIsDesktop(window.innerWidth >= 900);
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  return (
    <div className="h-screen w-full max-w-full flex flex-col overflow-x-hidden bg-bg-default text-text-primary">
      <div className="h-[10vh] w-full shrink-0">
        {header}
      </div>

      <div className="h-[90vh] w-full max-w-full flex overflow-hidden">
        {isDesktop && leftPanel}
        {contentPanel}
      </div>
    </div>
  );
};

export default MainLayout;
