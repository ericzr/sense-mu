import { redirect } from "next/navigation";

export default function ProviderPage() {
  redirect("/me?view=producer");
}
