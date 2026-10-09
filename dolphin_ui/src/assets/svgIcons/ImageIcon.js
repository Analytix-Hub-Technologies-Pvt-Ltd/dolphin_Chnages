export const ImageIcon = ({ size = 20, color = "currentColor" }) => {
  const fillColor = color || "currentColor";
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 -2 20 20"
      version="1.1"
      xmlns="http://www.w3.org/2000/svg"
      fill={fillColor}
    >
      <g id="SVGRepo_bgCarrier" strokeWidth="0"></g>
      <g
        id="SVGRepo_tracerCarrier"
        strokeLinecap="round"
        strokeLinejoin="round"
      ></g>
      <g id="SVGRepo_iconCarrier">
        <title>image_picture [#971]</title>
        <desc>Created with Sketch.</desc>
        <g
          id="Page-1"
          stroke="none"
          strokeWidth="1"
          fill="none"
          fillRule="evenodd"
        >
          <g
            id="Dribbble-Light-Preview"
            transform="translate(-420.000000, -3881.000000)"
            fill={fillColor}
          >
            <g id="icons" transform="translate(56.000000, 160.000000)">
              <path
                d="M376.083,3725.667 C376.083,3724.562 376.978,3723.667 378.083,3723.667 C379.188,3723.667 380.083,3724.562 380.083,3725.667 C380.083,3726.772 379.188,3727.667 378.083,3727.667 C376.978,3727.667 376.083,3726.772 376.083,3725.667 L376.083,3725.667 Z M382,3733.086 L377.987,3729.074 L377.971,3729.089 L377.955,3729.074 L376.525,3730.504 L371.896,3725.876 L371.881,3725.892 L371.865,3725.876 L366,3731.741 L366,3723 L382,3723 L382,3733.086 Z M364,3737 L384,3737 L384,3721 L364,3721 L364,3737 Z"
                id="image_picture-[#971]"
              ></path>
            </g>
          </g>
        </g>
      </g>
    </svg>
  );
};
