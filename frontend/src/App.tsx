import { RouterProvider } from "react-router-dom";
import { Providers } from "./providers";
import { router } from "./router";
import { ReconnectingOverlay } from "./components/common/ReconnectingOverlay";
import { NotificationToaster } from "./components/common/NotificationToaster";
import { EtaReviewWsDispatcher } from "./components/common/EtaReviewWsDispatcher";

function App() {
  return (
    <Providers>
      <ReconnectingOverlay />
      <NotificationToaster />
      <EtaReviewWsDispatcher />
      <RouterProvider router={router} />
    </Providers>
  );
}

export default App;
