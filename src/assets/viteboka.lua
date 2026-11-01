-- Pandoc filter that cleans up Viteboka article HTML for Discord embeds

local base_url = "https://viteboka.studentersamfundet.no"

function Table() return {} end
function Figure() return {} end
function Image() return {} end
function LineBreak() return pandoc.Space() end

function Link(link)
  -- Links to pages that don't exist, and links that only wrapped a removed image
  if link.classes:includes("new") or #link.content == 0 then
    return link.content
  end

  if link.target:sub(1, 1) == "/" then
    link.target = base_url .. link.target
  end
  link.title = ""
  return link
end
